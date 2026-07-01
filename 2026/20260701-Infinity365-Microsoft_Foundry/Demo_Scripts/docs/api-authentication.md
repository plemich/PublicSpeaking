# API-Authentifizierung (Beispiel-Doku für die Demo)

Unsere interne REST-API nutzt OAuth 2.0 mit Microsoft Entra ID. Es gibt keine
statischen API-Keys mehr.

## Schritte
1. Registriere deine App in Microsoft Entra ID und notiere Client-ID und Tenant-ID.
2. Fordere ein Token vom Token-Endpoint an (Client-Credentials-Flow für Service-zu-Service):
   `POST https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token`
   mit `grant_type=client_credentials`, `scope=api://<app-id>/.default`.
3. Sende das Bearer-Token im Header jeder Anfrage:
   `Authorization: Bearer <token>`.

## Hinweise
- Tokens sind 60 Minuten gültig; cache sie und erneuere rechtzeitig.
- Für lokale Entwicklung kannst du `az login` und DefaultAzureCredential nutzen.
- Niemals Secrets im Code ablegen — nutze Managed Identity in Azure.

## Rate Limits
Pro Client gelten 1.000 Requests/Minute. Bei Überschreitung kommt HTTP 429
mit `Retry-After`-Header.
