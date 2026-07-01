"""
Stufe 2b — Full Control & Orchestrierung (Agent Framework)
==========================================================
Das "Full-Control"-Szenario: eigener Orchestrierungs-Code statt Klickmenue.
Der Agent (Microsoft Agent Framework) bekommt ZWEI selbstgeschriebene Werkzeuge
und entscheidet bei der mehrstufigen Frage selbst, welches er wann ruft:
  - search_api_docs(...)   -> RAG-Retrieval direkt gegen den Azure-AI-Search-Index
  - get_service_status(...) -> lokale Status-Funktion

Hinweis: Wir rufen den Index hier ueber eine eigene Funktion ab (azure-search-documents),
statt ueber das fertige Hosted-AI-Search-Tool des Frameworks. Das ist bewusst:
(1) es zeigt die volle Kontrolle ueber Retrieval + Orchestrierung, und
(2) es umgeht einen Serialisierungs-Bug im Preview-Paket agent-framework-foundry 1.10.0.

Voraussetzungen:
  - Index aus Stufe 1.
  - pip install agent-framework-foundry azure-search-documents azure-identity
  - az login
  - .env: FOUNDRY_PROJECT_ENDPOINT, FOUNDRY_MODEL, SEARCH_ENDPOINT, SEARCH_INDEX_NAME, (optional) SEARCH_API_KEY

Start:  python 03_orchestration.py
"""
import asyncio, os
# Preview-Bug umgehen: das eingebaute Tracing von agent-framework crasht beim
# Serialisieren von Tool-Definitionen. Vor dem Import abschalten.
# Server-seitige Traces in Foundry (Agents > Traces) sind davon unberuehrt.
os.environ.setdefault("ENABLE_INSTRUMENTATION", "false")

from dotenv import load_dotenv
from agent_framework import Agent, tool
from agent_framework.foundry import FoundryChatClient
from azure.identity import AzureCliCredential
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizableTextQuery

load_dotenv()
SEARCH_ENDPOINT = os.environ["SEARCH_ENDPOINT"]
SEARCH_INDEX    = os.environ.get("SEARCH_INDEX_NAME", "api-docs-index")
SEARCH_API_KEY  = os.environ.get("SEARCH_API_KEY")     # leer = keyless

credential  = AzureCliCredential()                     # FoundryChatClient nutzt das + FOUNDRY_* aus .env
search_cred = AzureKeyCredential(SEARCH_API_KEY) if SEARCH_API_KEY else credential
search = SearchClient(SEARCH_ENDPOINT, SEARCH_INDEX, search_cred)


# --- Werkzeug 1: eigenes RAG-Retrieval (hybrid: Volltext + Vektor) ---
@tool
def search_api_docs(query: str) -> str:
    """Durchsucht die interne API-Doku und gibt belegte Auszuege mit Quelle zurueck."""
    vq = VectorizableTextQuery(text=query, k_nearest_neighbors=5, fields="chunk_vector")
    hits = search.search(search_text=query, vector_queries=[vq],
                         select=["title", "url", "chunk"], top=5)
    out = [f"Quelle: {h['title']} ({h['url']})\n{h['chunk'][:600]}" for h in hits]
    return "\n\n---\n\n".join(out) if out else "Keine Treffer im Index."


# --- Werkzeug 2: lokale Status-Funktion ---
@tool
def get_service_status(service_name: str) -> str:
    """Gibt den aktuellen Betriebsstatus eines internen Dienstes zurueck."""
    # Demo-Stub — hier wuerde ein echter Status-/Monitoring-Call stehen.
    return f"{service_name}: operational (99.95% uptime, letzte 24h)"


async def main() -> None:
    agent = Agent(
        client=FoundryChatClient(credential=credential),   # liest FOUNDRY_PROJECT_ENDPOINT + FOUNDRY_MODEL
        instructions=(
            "Du bist ein technischer Wissens-Agent. Nutze search_api_docs fuer Wissensfragen "
            "und get_service_status fuer Betriebsstatus. Zitiere immer die Quelle (Titel/URL) "
            "aus den Suchergebnissen."
        ),
        tools=[search_api_docs, get_service_status],
    )

    # Mehrstufige Frage -> der Agent orchestriert beide Tools selbst.
    result = await agent.run(
        "Wie authentifiziere ich mich gegen die API - und laeuft der Auth-Service gerade stabil?"
    )
    print(result.text)


if __name__ == "__main__":
    asyncio.run(main())

# ----------------------------------------------------------------------------
# SKALIERUNG / PRODUKTION — denselben Agenten als Hosted Agent betreiben:
# Foundry uebernimmt managed Endpoint, Auto-Scaling, Identitaet, Observability.
#   from agent_framework_foundry_hosting import ResponsesHostServer
#   server = ResponsesHostServer(agent)
#   server.run()
# Deploy via Azure Developer CLI (azd) — siehe README, Stufe 2b.
# ----------------------------------------------------------------------------
