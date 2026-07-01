# Foundry Live-Demo — Scripts & Story

**Die Story:** Wir bauen einen technischen Wissens-Agenten über die interne API-Doku — vom Index bis ins M365-Frontend. Eine einzige Frage zieht sich durch alle Stufen:

> „Wie authentifiziere ich mich gegen die API?"

Der rote Faden zeigt die vier Dinge, um die es in der Session geht: **komplexe RAG-Architektur**, **Full Control & Skalierbarkeit** durch eigene Orchestrierung, **Tracing/Observability** und die **Brücke zu den M365-Frontends**.

| Stufe | Script | Szenario | Botschaft |
|---|---|---|---|
| 1 | `01_build_index.py` | Wissensbasis als komplexer RAG-Index | RAG-Qualität entscheidet sich beim Index |
| 2 | `02_agent_code.py` | Managed Prompt Agent + Grounding + **Tracing** | Reinschauen statt raten |
| 2b | `03_orchestration.py` | **Full Control**: eigene Orchestrierung, mehrere Tools, Hosted Agent | Kontrolle + Skalierung |
| 3 | `04_call_agent_api.py` / `04_bridge_curl.sh` | **Brücke zu M365** / beliebiges Frontend | Gleicher Agent, anderes Frontend |

---

## Setup (einmalig)

macOS/Linux (zsh/bash) — jede Zeile einzeln ausführen, Kommentarzeilen nicht mitkopieren:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
open -e .env
az login
```

Hinweise: Auf macOS heißt der Interpreter `python3` (nicht `python`); im aktivierten venv funktioniert dann `python`/`pip`. Auf Windows: `python -m venv .venv` und `.venv\Scripts\activate`. Fehlt ein Tool: `brew install python` bzw. `brew install azure-cli`. In zsh ist `#` interaktiv kein Kommentar — keine `# ...`-Notizen an Befehle anhängen.

**Voraussetzungen** (Details in `Foundry_Setup_Anleitung.docx`): Foundry-Resource + Projekt, ein Chat-Modell und `text-embedding-3-large` deployed, ein Azure-AI-Search-Service, und eine Connection *Projekt → Azure AI Search* (Name in `.env`).

**Nötige Rollen (keyless):** auf dem Search-Service `Search Index Data Contributor` + `Search Service Contributor`; auf der OpenAI/Foundry-Resource `Cognitive Services OpenAI User`; für Traces `Log Analytics Reader` auf der App-Insights-Resource.

---

## Stufe 1 · Komplexe RAG-Architektur — `01_build_index.py`

Das Herzstück. Das Script legt einen **Hybrid-Index** an und befüllt ihn:

- **Vektorsuche** (HNSW, Cosine) auf `chunk_vector` (3072 Dim., text-embedding-3-large)
- **Semantic Ranking** als Reranker über Titel + Inhalt
- **Integrierter Vectorizer** im Index → der Agent vektorisiert die *Query* zur Laufzeit selbst (kein eigener Embedding-Code im Agenten nötig)
- **Citations-Feld** `url` (retrievable), damit Antworten belegt sind
- **Chunking** 512 Token / 20 % Overlap (der Qualitäts-Hebel)

Dokumente liegen in `./docs` (Beispiel `api-authentication.md` ist dabei). Reihenfolge: Index anlegen → chunken → embedden → hochladen → Verifikations-Query.

```bash
python 01_build_index.py
```

> Komplexer ausbaubar: mehrere Knowledge Sources, Integrated Vectorization per Indexer/Skillset (pull aus Blob), oder Foundry IQ als managed Knowledge Base. Für die Live-Demo bleibt der Push-Weg am robustesten, weil nichts auf einen Indexer-Lauf warten muss.

## Stufe 2 · Managed Agent + Tracing — `02_agent_code.py`

Ein **Prompt Agent** (managed Runtime) mit dem Index als Grounding-Tool, gestreamte Antwort mit Citations. Mit `--trace` schreibt der Lauf Traces nach Application Insights — danach im Portal unter **Agents → Traces** der Waterfall: welcher Chunk, wie viele Tokens, wie viel Latenz.

```bash
python 02_agent_code.py            # Antwort + Citations
python 02_agent_code.py --trace    # zusätzlich client-seitiges Tracing
```

## Stufe 2b · Full Control & Skalierung — `03_orchestration.py`

Hier kippt die Story von „managed" zu **„volle Kontrolle"**: Orchestrierung im Code mit dem **Microsoft Agent Framework**. Der Agent bekommt **zwei Werkzeuge** (RAG-Suche + lokale Status-Funktion) und entscheidet selbst, wann er welches ruft — sichtbar an der mehrstufigen Frage.

```bash
python 03_orchestration.py
```

**Skalierung:** Derselbe Code läuft als **Hosted Agent** — Foundry betreibt ihn mit managed Endpoint, Auto-Scaling und eigener Identität (`ResponsesHostServer`, Deploy via `azd`; Skelett am Ende des Scripts).

## Stufe 3 · Brücke zu M365 — `04_call_agent_api.py` / `04_bridge_curl.sh`

Derselbe Agent, aufgerufen wie aus einer App — gleiche Frage, gleiche Antwort, anderes Frontend.

```bash
python 04_call_agent_api.py        # via SDK (wie eine Web-/Teams-App)
PROJECT_ENDPOINT=... bash 04_bridge_curl.sh   # via reinem HTTP (Postman/Integrationen)
```

**In Teams / M365** (im Portal bzw. Teams Toolkit, nicht skriptbar): den Agenten als **Custom Engine Agent** veröffentlichen, oder über **Work IQ** / das **SharePoint-Tool** direkt an M365-Inhalte anbinden. **A2A-Endpoints** erlauben Agent-zu-Agent-Aufrufe.

---

## Demo-Ablauf (empfohlen)

1. `01` vorab laufen lassen (Index ist „pre-deployed") — live nur die Konfiguration zeigen.
2. `02 --trace` einmal vor der Session feuern, damit der Trace im Portal schon da ist (erscheint nach 2–5 Min).
3. Live: `02` (Grounding + Tracing) → `03` (Orchestrierung/Full Control) → `04` (M365-Brücke).
4. Fallback bereithalten: `04_bridge_curl.sh`, falls das Portal hakt.

## Quellen (Microsoft Learn)

- Index/Vektorsuche: learn.microsoft.com/azure/search/vector-search-how-to-create-index
- Integrated Vectorization: learn.microsoft.com/azure/search/vector-search-integrated-vectorization
- AI-Search-Tool für Agenten: learn.microsoft.com/azure/foundry/agents/how-to/tools/ai-search
- Responses API / Agent Framework: learn.microsoft.com/azure/foundry/agents/quickstarts/responses-api
- Tracing-Setup: learn.microsoft.com/azure/foundry/observability/how-to/trace-agent-setup
