#!/usr/bin/env bash
# Stufe 3 — dieselbe Frage per reinem HTTP (z.B. fuer Postman/Integrationen).
# Zeigt: das Frontend ist austauschbar, der Agent bleibt derselbe.
set -euo pipefail

# PROJECT_ENDPOINT z.B. https://<res>.services.ai.azure.com/api/projects/<project>
: "${PROJECT_ENDPOINT:?bitte PROJECT_ENDPOINT setzen}"
TOKEN=$(az account get-access-token --resource https://ai.azure.com --query accessToken -o tsv)

curl -sS -X POST "${PROJECT_ENDPOINT}/responses?api-version=2025-05-01-preview" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
        "input": "Wie authentifiziere ich mich gegen die API?",
        "agent_reference": { "name": "api-docs-agent", "type": "agent_reference" }
      }'
echo
