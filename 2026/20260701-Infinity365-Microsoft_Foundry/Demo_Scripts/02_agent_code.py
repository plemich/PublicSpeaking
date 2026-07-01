"""
Stufe 2 — Agent im Code (mit Tracing)
=====================================
Erstellt einen Foundry Prompt Agent, haengt den Azure-AI-Search-Index als
Grounding-Tool an, feuert eine Query ueber die Responses API und zeigt die
Antwort + Citations. Optional: client-seitiges Tracing nach Application Insights.

Voraussetzungen:
  - Index aus Stufe 1 existiert.
  - Connection (Projekt -> Azure AI Search) ist im Projekt angelegt (Name in .env).
  - pip install "azure-ai-projects>=2.0.0" azure-identity
  - Auth: az login (DefaultAzureCredential)

Start:           python 02_agent_code.py
Mit Tracing:     python 02_agent_code.py --trace
"""
import os, sys
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    PromptAgentDefinition, AzureAISearchTool, AzureAISearchToolResource,
    AISearchIndexResource, AzureAISearchQueryType,
)

load_dotenv()
PROJECT_ENDPOINT = os.environ["PROJECT_ENDPOINT"]   # https://<res>.services.ai.azure.com/api/projects/<project>
CHAT_MODEL       = os.environ.get("CHAT_MODEL", "gpt-4.1-mini")
INDEX_NAME       = os.environ.get("SEARCH_INDEX_NAME", "api-docs-index")
CONNECTION_NAME  = os.environ["SEARCH_CONNECTION_NAME"]
QUESTION         = "Wie authentifiziere ich mich gegen die API?"

cred = DefaultAzureCredential()
project = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=cred)

# --- optional: client-seitiges Tracing einschalten ---
if "--trace" in sys.argv:
    os.environ["AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING"] = "true"
    from azure.monitor.opentelemetry import configure_azure_monitor
    conn = project.telemetry.get_application_insights_connection_string()
    configure_azure_monitor(connection_string=conn)
    print("Tracing aktiv -> Traces erscheinen nach ~2-5 Min unter Agents > Traces")

openai = project.get_openai_client()

# Connection-Name -> Connection-ID aufloesen
conn_id = project.connections.get(CONNECTION_NAME).id

# --- Agent definieren: System Prompt + AI-Search-Grounding-Tool ---
agent = project.agents.create_version(
    agent_name="api-docs-agent",
    definition=PromptAgentDefinition(
        model=CHAT_MODEL,
        instructions=(
            "Du bist ein technischer Wissens-Agent ueber unsere interne API-Doku. "
            "Antworte NUR aus dem Index. Gib immer Citations an. "
            "Wenn nichts gefunden wird, sage das ehrlich."
        ),
        tools=[AzureAISearchTool(azure_ai_search=AzureAISearchToolResource(indexes=[
            AISearchIndexResource(
                project_connection_id=conn_id,
                index_name=INDEX_NAME,
                query_type=AzureAISearchQueryType.VECTOR_SEMANTIC_HYBRID,  # Default; nutzt Index-Vectorizer
                top_k=5,
            )
        ]))],
    ),
)
print(f"Agent: {agent.name} (Version {agent.version})\n")

# --- Query feuern (gestreamt) ---
stream = openai.responses.create(
    stream=True,
    tool_choice="required",   # Tool MUSS feuern -> deterministisch fuer die Demo
    input=QUESTION,
    extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
)
print(f"Frage: {QUESTION}\nAntwort: ", end="")
for event in stream:
    if event.type == "response.output_text.delta":
        print(event.delta, end="", flush=True)
    elif event.type == "response.completed":
        print("\n\nCitations:")
        for item in event.response.output:
            for c in getattr(item, "content", []) or []:
                for ann in getattr(c, "annotations", []) or []:
                    if getattr(ann, "type", "") == "url_citation":
                        print(f"  - {ann.title}: {ann.url}")
print("\nFertig. Trace im Portal pruefen: Agents > Traces (Token, Latenz, gezogener Chunk).")
