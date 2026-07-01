"""
Stufe 3 — Bruecke zu M365 / anderes Frontend
============================================
Derselbe Agent (aus Stufe 2), aufgerufen wie aus einer beliebigen App.
Kernbotschaft der Demo: gleiche Frage, gleicher Index, gleiche Antwort -
nur ein anderes Frontend.

Dieses Script ruft den bereits angelegten Agenten 'api-docs-agent' ueber die
Responses API auf (kein erneutes Anlegen). Fuer Teams als Custom Engine Agent
oder Work IQ / SharePoint-Tool: siehe README (im Portal/Teams Toolkit, nicht skriptbar).

Start:  python 03_call_agent_api.py
"""
import os
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

load_dotenv()
PROJECT_ENDPOINT = os.environ["PROJECT_ENDPOINT"]
AGENT_NAME       = os.environ.get("AGENT_NAME", "api-docs-agent")
QUESTION         = "Wie authentifiziere ich mich gegen die API?"   # dieselbe Frage wie in Stufe 2

project = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=DefaultAzureCredential())
openai = project.get_openai_client()

# Konversation (Responses API) - so wuerde es auch eine Web-/Teams-App tun
conversation = openai.conversations.create()
response = openai.responses.create(
    conversation=conversation.id,
    input=QUESTION,
    extra_body={"agent_reference": {"name": AGENT_NAME, "type": "agent_reference"}},
)
print(f"Frontend-Aufruf (App/Teams/API) -> Agent '{AGENT_NAME}'")
print(f"Frage:   {QUESTION}")
print(f"Antwort: {response.output_text}")
openai.conversations.delete(conversation_id=conversation.id)
