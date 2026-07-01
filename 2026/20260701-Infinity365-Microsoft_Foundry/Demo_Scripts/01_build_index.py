"""
Stufe 1 — Index aufbauen
========================
Erstellt einen Azure-AI-Search-Index mit Vektor- + Semantic-Suche und einem
AzureOpenAI-Vectorizer (damit der Foundry-Agent zur Query-Zeit selbst vektorisiert),
liest lokale Dokumente aus ./docs, zerlegt sie in Chunks (512 Token, 20% Overlap),
erzeugt Embeddings (text-embedding-3-large) und lädt sie in den Index.

Auth: keyless via DefaultAzureCredential (empfohlen). Nötige Rollen:
  - auf dem Search-Service:  Search Index Data Contributor  +  Search Service Contributor
  - auf der OpenAI/Foundry-Resource:  Cognitive Services OpenAI User
Stand: azure-search-documents (aktuelle GA), text-embedding-3-large => 3072 Dimensionen.

Start:  python 01_build_index.py
"""
import os, glob, pathlib
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex, SearchField, SearchFieldDataType, SimpleField, SearchableField,
    VectorSearch, HnswAlgorithmConfiguration, HnswParameters, VectorSearchAlgorithmMetric,
    VectorSearchProfile, AzureOpenAIVectorizer, AzureOpenAIVectorizerParameters,
    SemanticConfiguration, SemanticPrioritizedFields, SemanticField, SemanticSearch,
)
from openai import AzureOpenAI

load_dotenv()
SEARCH_ENDPOINT   = os.environ["SEARCH_ENDPOINT"]            # https://<svc>.search.windows.net
INDEX_NAME        = os.environ.get("SEARCH_INDEX_NAME", "api-docs-index")
AOAI_ENDPOINT     = os.environ["AOAI_ENDPOINT"]             # https://<res>.openai.azure.com  (oder Foundry-Services-Endpoint)
EMBED_DEPLOYMENT  = os.environ.get("EMBED_DEPLOYMENT", "text-embedding-3-large")
EMBED_MODEL       = os.environ.get("EMBED_MODEL", "text-embedding-3-large")
EMBED_DIMS        = int(os.environ.get("EMBED_DIMS", "3072"))   # text-embedding-3-large = 3072
CHUNK_TOKENS      = 512
CHUNK_OVERLAP     = 100                                          # ~20 %

# Optionale Keys (falls der Search-Service / die OpenAI-Resource key-basiert ist).
# Sind sie gesetzt, wird Key-Auth genutzt; sonst keyless (DefaultAzureCredential / Entra).
SEARCH_API_KEY = os.environ.get("SEARCH_API_KEY")   # Admin-Key des Azure-AI-Search-Service
AOAI_API_KEY   = os.environ.get("AOAI_API_KEY")     # Key der OpenAI/Foundry-Resource

from azure.core.credentials import AzureKeyCredential
azure_cred  = DefaultAzureCredential()
search_cred = AzureKeyCredential(SEARCH_API_KEY) if SEARCH_API_KEY else azure_cred

# ---------- 1) Index anlegen (Vektor + Semantic + Vectorizer) ----------
def create_index():
    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SearchableField(name="title", type=SearchFieldDataType.String, filterable=True),
        # zitierbarer Inhalt: searchable + retrievable
        SearchableField(name="chunk", type=SearchFieldDataType.String),
        # Quellen-Feld fuer Citations (eines von url/sourceUrl/filePath/path/folderPath)
        SimpleField(name="url", type=SearchFieldDataType.String, retrievable=True),
        # Vektorfeld
        SearchField(
            name="chunk_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True, vector_search_dimensions=EMBED_DIMS,
            vector_search_profile_name="hnsw-aoai",
        ),
    ]
    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(
            name="hnsw",
            parameters=HnswParameters(m=4, ef_construction=400, ef_search=500,
                                      metric=VectorSearchAlgorithmMetric.COSINE),
        )],
        profiles=[VectorSearchProfile(
            name="hnsw-aoai", algorithm_configuration_name="hnsw", vectorizer_name="aoai",
        )],
        # Vectorizer = Query-Zeit-Vektorisierung. Der Foundry-AI-Search-Tool nutzt das,
        # damit query_type=vector_semantic_hybrid ohne eigenen Embedding-Code funktioniert.
        vectorizers=[AzureOpenAIVectorizer(
            vectorizer_name="aoai",
            parameters=AzureOpenAIVectorizerParameters(
                resource_url=AOAI_ENDPOINT, deployment_name=EMBED_DEPLOYMENT, model_name=EMBED_MODEL,
                # Key mitgeben, falls vorhanden -> Query-Zeit-Vektorisierung ohne Managed Identity
                **({"api_key": AOAI_API_KEY} if AOAI_API_KEY else {}),
            ),
        )],
    )
    semantic = SemanticSearch(configurations=[SemanticConfiguration(
        name="sem", prioritized_fields=SemanticPrioritizedFields(
            title_field=SemanticField(field_name="title"),
            content_fields=[SemanticField(field_name="chunk")],
        ),
    )])
    index = SearchIndex(name=INDEX_NAME, fields=fields,
                        vector_search=vector_search, semantic_search=semantic)
    SearchIndexClient(endpoint=SEARCH_ENDPOINT, credential=search_cred).create_or_update_index(index)
    print(f"Index '{INDEX_NAME}' erstellt/aktualisiert.")

# ---------- 2) Chunking ----------
def chunk_text(text):
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        toks = enc.encode(text)
        step = CHUNK_TOKENS - CHUNK_OVERLAP
        for i in range(0, len(toks), step):
            yield enc.decode(toks[i:i + CHUNK_TOKENS])
    except ImportError:
        # Fallback ohne tiktoken: ~4 Zeichen/Token
        size, step = CHUNK_TOKENS * 4, (CHUNK_TOKENS - CHUNK_OVERLAP) * 4
        for i in range(0, len(text), step):
            yield text[i:i + size]

# ---------- 3) Embedding + Upload ----------
def ingest():
    if AOAI_API_KEY:
        aoai = AzureOpenAI(azure_endpoint=AOAI_ENDPOINT, api_key=AOAI_API_KEY, api_version="2024-10-21")
    else:
        token_provider = get_bearer_token_provider(azure_cred, "https://cognitiveservices.azure.com/.default")
        aoai = AzureOpenAI(azure_endpoint=AOAI_ENDPOINT, azure_ad_token_provider=token_provider,
                           api_version="2024-10-21")
    search = SearchClient(endpoint=SEARCH_ENDPOINT, index_name=INDEX_NAME, credential=search_cred)

    files = glob.glob("docs/**/*.md", recursive=True) + glob.glob("docs/**/*.txt", recursive=True)
    if not files:
        print("Keine Dokumente in ./docs gefunden (*.md, *.txt). Lege Beispiel-Doku an oder kopiere deine Dateien dorthin.")
        return
    docs = []
    for path in files:
        name = pathlib.Path(path).stem
        text = pathlib.Path(path).read_text(encoding="utf-8", errors="ignore")
        for i, chunk in enumerate(chunk_text(text)):
            if not chunk.strip():
                continue
            vector = aoai.embeddings.create(model=EMBED_DEPLOYMENT, input=[chunk]).data[0].embedding
            docs.append({
                "id": f"{name}-{i}",
                "title": name,
                "chunk": chunk,
                "url": f"https://docs.example.com/{name}#chunk{i}",   # echtes Quell-URL hier einsetzen
                "chunk_vector": vector,
            })
    # in Batches hochladen
    for b in range(0, len(docs), 100):
        search.upload_documents(documents=docs[b:b + 100])
    print(f"{len(docs)} Chunks aus {len(files)} Dokument(en) hochgeladen.")

# ---------- 4) Verifikation: Vektor-Query ----------
def verify():
    from azure.search.documents.models import VectorizableTextQuery
    search = SearchClient(endpoint=SEARCH_ENDPOINT, index_name=INDEX_NAME, credential=search_cred)
    vq = VectorizableTextQuery(text="Wie authentifiziere ich mich gegen die API?",
                               k_nearest_neighbors=3, fields="chunk_vector")
    results = search.search(search_text=None, vector_queries=[vq], select=["title", "url"], top=3)
    print("Top-Treffer (Query-Zeit-Vektorisierung via Index-Vectorizer):")
    for r in results:
        print(f"  - {r['title']}  ({r['url']})  score={r['@search.score']:.3f}")

if __name__ == "__main__":
    create_index()
    ingest()
    verify()
