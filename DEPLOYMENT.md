# Deployment foundation and authentication

This repository contains multi-stage Dockerfiles for the Next.js web app and FastAPI API. The web app uses OpenID Connect Authorization Code flow with PKCE through a public browser client.

## Web container

Build from the web app directory:

```bash
cd apps/web
docker build \
  --build-arg NEXT_PUBLIC_API_URL=https://api.example.com \
  --build-arg NEXT_PUBLIC_OIDC_AUTHORITY=https://identity.example.com \
  --build-arg NEXT_PUBLIC_OIDC_CLIENT_ID=carbon-esg-web \
  -t carbon-esg-web .
docker run --rm -p 3000:3000 carbon-esg-web
```

Configure the OIDC provider as a public SPA client:
- Authorization Code flow with PKCE (S256).
- Redirect URI: `https://app.example.com/auth/callback`.
- Post-logout redirect URI: `https://app.example.com/`.
- Allowed web origin: `https://app.example.com`.
- Scopes: `openid profile email` plus the provider-specific API access scope configured as `NEXT_PUBLIC_OIDC_API_SCOPE`.
- Request the API audience configured as `NEXT_PUBLIC_OIDC_AUDIENCE`; it must match the API `OIDC_AUDIENCE` claim.
- Do not configure or ship a client secret to the browser.

The browser stores OIDC state and user session data in session storage. App sign-out removes the local browser session; it does not necessarily terminate the identity provider SSO session. Silent refresh and refresh-token issuance are intentionally disabled in this foundation; expired sessions require re-authentication. Use a short access-token lifetime and deploy a strict Content Security Policy before production.

The API URL, OIDC authority, and OIDC client ID are public browser configuration. Never put credentials, database URLs, signing keys, or private tokens in `NEXT_PUBLIC_*` variables.

## API container

Build from the API directory:

```bash
cd apps/api
docker build -t carbon-esg-api .
docker run --rm -p 8000:8000 \
  -e ENVIRONMENT=production \
  -e DATABASE_URL='postgresql+psycopg://carbon_esg_app:STRONG_PASSWORD@db.example.com/carbon_esg' \
  -e CORS_ORIGINS=https://app.example.com \
  -e OIDC_ISSUER=https://identity.example.com/ \
  -e OIDC_AUDIENCE=carbon-esg-api \
  -e OIDC_JWKS_URL=https://identity.example.com/.well-known/jwks.json \
  carbon-esg-api
```

Configure `CORS_ORIGINS` as a comma-separated allow-list of exact trusted web origins. Do not use a wildcard. Configure the API issuer, audience, and JWKS URL to match the OIDC provider and API resource registration. First, execute `apps/api/scripts/bootstrap_database_roles.sql` as the PostgreSQL administrator and set independent strong passwords for `carbon_esg_migrator` and `carbon_esg_app`. Run Alembic migrations separately with `MIGRATION_DATABASE_URL=postgresql+psycopg://carbon_esg_migrator:...@db.example.com/carbon_esg alembic upgrade head`. After migrations, execute `psql "$MIGRATION_DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/bootstrap_runtime_role.sql` as `carbon_esg_migrator`. Never pass either privileged credential into the running API container. The migration role is a separate, tightly controlled `BYPASSRLS` role used only for schema migrations and cross-tenant maintenance; it is not a superuser. The application role must remain `NOSUPERUSER`, `NOBYPASSRLS`, and must not own tenant tables. It receives read access, inserts only for required workflows, and column-level updates only for factor approval; it cannot delete audit records, snapshots, or factors, nor create tenants or memberships. The API runtime connects only as `carbon_esg_app`; Alembic uses `MIGRATION_DATABASE_URL`.

## First-user and organization provisioning

The API validates OIDC tokens but does not automatically create users or organizations. Before a user can access a workspace, an authorized operator must provision:
1. A `users` row with the exact OIDC `auth_issuer` and `auth_subject`, verified email, and active status.
2. A `tenants` row for the legal organization.
3. A `memberships` row linking that user and tenant with an approved role.
4. The tenant UUID, which the user enters after signing in.

Do not accept tenant IDs or role claims as proof of authorization. The API verifies membership and enforces tenant context server-side. The tenant UUID is a selector only.

## CI checks

GitHub Actions currently runs PostgreSQL 16 migrations, database/RLS checks, API tests, production dependency audit, TypeScript checks, and Next.js production build. A green CI run does not replace production identity-provider configuration, infrastructure review, or security testing.

## Remaining production release gates

This repository is still a production-readiness work in progress. Do not accept confidential customer data or make assurance-ready ESG claims until the following are complete and independently reviewed:

1. Production OIDC provider setup, user/tenant provisioning workflow, MFA policy, session revocation and tested account recovery.
2. Production non-owner PostgreSQL runtime role, least-privilege grants, cross-tenant write/read tests for every tenant table and every API route.
3. Evidence Vault with private object storage, upload limits, content-type validation, malware scanning, retention and restore testing.
4. Complete activity review workflow and immutable audit coverage for every business mutation.
5. Scope 1, Scope 2 dual reporting with contractual-instrument quality controls, and all material Scope 3 categories.
6. Reviewed Mongolia-specific emission-factor registry with source, geography, year, units, gases/GWP basis, version, validity and human approval.
7. Legal registry consolidated official text, amendment history, effective dates, source checksums and legal reviewer workflow. Standard full texts require appropriate licensing.
8. PDF/XLSX bilingual reports, traceable evidence references and independent accounting/assurance review.
9. Rate limiting, request-size limits, idempotency, secrets management, CSP, SAST, container scanning, SBOM, dependency monitoring and security incident procedures.
10. Automated encrypted backups, tested restore drills, documented RPO/RTO, monitoring and alerting.
11. Staging deployment, TLS, rollback procedure, load tests, disaster-recovery exercise and independent penetration test.

Free hosting may be appropriate for development or a demo only until persistence, data residency, access controls, backups and recovery commitments have been verified.
