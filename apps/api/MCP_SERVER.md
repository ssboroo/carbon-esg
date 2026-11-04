# Carbon ESG MCP server

## What it does

The MCP adapter allows compatible AI clients to call a controlled set of Carbon ESG functions. This first release is **read-only plus calculation preview**.

### Tools

- `carbon_esg_health`: check API health.
- `calculate_scope12_preview`: validate supplied Scope 1/2 data and sourced emission factors, then call the existing deterministic engine.
- `search_mongolia_legal_registry`: search the imported Mongolian legal-act index.
- `list_esg_standards`: search standards metadata. No copyrighted MNS/ISO full text is distributed.

## Security boundary

- Uses local MCP stdio transport; the AI host launches the process.
- The server calls only fixed API paths; tool callers cannot provide arbitrary URLs.
- No database credentials, tenant data, file uploads, user management or write operations are exposed.
- `CARBON_ESG_API_TOKEN` optionally adds a bearer token to API calls. This does not replace API-side authentication; the current legal/standards endpoints are not tenant-authenticated.
- Never put API/database passwords in tool arguments or source control.
- AI must not invent emission factors. Every calculation input requires factor source, year, unit and version.
- Results are previews, not approved, signed or persisted inventory records.

## Run locally

From `apps/api`:

```bash
python -m pip install -r requirements.txt
export CARBON_ESG_API_URL=http://127.0.0.1:8000
python -m app.mcp_server
```

Run FastAPI separately. MCP talks to it over localhost.

## MCP client configuration

For a compatible local MCP client, configure the launch command (the exact settings location varies by client):

```json
{
  "mcpServers": {
    "carbon-esg": {
      "command": "python",
      "args": ["-m", "app.mcp_server"],
      "cwd": "/absolute/path/to/carbon-esg/apps/api",
      "env": {
        "CARBON_ESG_API_URL": "http://127.0.0.1:8000"
      }
    }
  }
}
```

This is a local stdio server. ChatGPT remote MCP connections generally need a reachable HTTPS endpoint and authentication; this implementation is not publicly hosted and does not yet provide remote transport.

## Next security milestones

1. OIDC login and server-side organization membership authorization.
2. Short-lived audience-restricted MCP tokens; tenant context only from verified identity claims.
3. Tenant-scoped read tools and RLS tests under a non-owner runtime database role.
4. Write tools only after role checks, explicit user confirmation, idempotency and immutable audit events.
5. Remote Streamable HTTP only after TLS, OAuth, rate limits, origin checks, secrets and deployment controls.
