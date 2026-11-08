# Carbon ESG

Mongolian-first ESG and greenhouse-gas accounting platform.

## Architecture

- `apps/web`: Next.js + TypeScript frontend
- `apps/api`: Python FastAPI backend
- Authentication: Neon Managed Better Auth (email/password) with a same-origin Next.js proxy; FastAPI verifies EdDSA JWTs using Neon JWKS.
- PostgreSQL multi-tenant persistence foundation is defined with SQLAlchemy models, Alembic migration, tenant-scoped composite foreign keys, and PostgreSQL row-level security. The current calculation endpoint remains stateless until authentication and tenant-aware persistence routes are implemented.
- Emissions are calculated deterministically from activity data and a supplied, documented emission factor.
- AI may assist with document extraction and report narratives, but must never invent emission factors or authoritative calculation results.

## Current API capability

The API currently supports a first-pass Scope 1 and Scope 2 calculation endpoint:

- `GET /health` — service health
- `GET /v1/auth/me` — protected identity verification; requires `Authorization: Bearer <Neon JWT>`
- `GET /v1/organizations` — list organizations for the verified user (requires migrated PostgreSQL schema and `DATABASE_URL`)
- `POST /v1/organizations` — create an organization and its initial owner membership atomically (requires migrated PostgreSQL schema and `DATABASE_URL`)
- `POST /v1/calculations` — calculate an inventory from supplied activity records and emission factors
- `GET /docs` — interactive API documentation

Each record must include its own emission factor, denominator unit, source name, HTTPS source URL, year, and version. The activity unit must match the factor denominator. The API intentionally ships with **no hard-coded emission factors**.

The factor value is interpreted as `kgCO2e per activity unit`. Results are returned in kgCO2e and tCO2e. The current calculation endpoint does not yet persist records or implement the Scope 2 market-based/location-based reporting distinction.

### Example request

```json
{
  "reporting_period_start": "2026-01-01",
  "reporting_period_end": "2026-12-31",
  "records": [
    {
      "name": "Purchased electricity",
      "scope": "scope_2",
      "category": "purchased_electricity",
      "activity_amount": "1000",
      "activity_unit": "kWh",
      "emission_factor_kgco2e_per_unit": "0.5",
      "factor_unit": "kWh",
      "factor_source_name": "Example source — replace with a verified factor",
      "factor_source_url": "https://example.org/emission-factors",
      "factor_year": 2026,
      "factor_version": "1.0"
    }
  ]
}
```

The factor in this example is illustrative only and must not be used for actual reporting.

## PostgreSQL persistence foundation (not yet wired to API routes)

The API now contains a tenant-scoped schema for organizations, memberships, versioned emission factors, inventories, activity records, calculation snapshots, and audit events. PostgreSQL row-level security requires transaction-local identity and organization context; membership discovery is scoped to the authenticated subject. Composite foreign keys prevent records from referencing another organization's inventory or emission factor. Emission-factor rows are immutable: corrections must be inserted as a new version.

Neon Managed Better Auth is provisioned on the Neon default branch. The web app includes email sign-up/sign-in, same-origin auth proxy, protected workspace, and sign-out. FastAPI validates EdDSA JWT signature, issuer, audience, expiry, and subject. The `GET /v1/auth/me` endpoint is the first protected integration check. Organization list/create routes now use transaction-local identity and tenant RLS context. They remain unavailable until the tenant migration is applied and a restricted runtime database role is configured. Do not expose tenant data routes until a verified identity-to-organization membership dependency sets both RLS contexts on every transaction. Use a restricted runtime database role; do not run the app as a superuser or a role with BYPASSRLS.

Set `DATABASE_URL` to Neon's pooled connection string for runtime requests. Set `DATABASE_URL_UNPOOLED` to the direct (non-pooler) string for migrations. Never commit either secret.

Run the first schema migration only after reviewing it against a Neon development branch:

```bash
cd apps/api
alembic upgrade head
```

The migration has not been applied to the shared Neon project. It is version-controlled and must be tested on a disposable Neon branch before any shared/main-branch application.

## Authentication configuration

Set `NEON_AUTH_BASE_URL` and `NEON_AUTH_COOKIE_SECRET` for the web service. The cookie secret must be at least 32 characters and server-only. Set `NEON_AUTH_BASE_URL` and `NEON_AUTH_JWKS_URL` for FastAPI. Localhost origins are pre-approved by Neon Auth; add the exact production HTTPS frontend origin to Neon Auth trusted domains after the Render URL exists.

## Local development

### API

```bash
cd apps/api
python -m venv .venv
# Activate the virtual environment, then:
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Run API unit tests:

```bash
cd apps/api
pytest
```

### Web

```bash
cd apps/web
npm install
npm run dev
```

## Accounting approach and limitations

The implementation follows the basic activity-data × documented-emission-factor calculation pattern described by the GHG Protocol. A production inventory still requires appropriate, region- and year-specific factors, transparent organizational and operational boundaries, data-quality controls, and review of applicable accounting methods. Scope 2 market-based/location-based accounting, database persistence, authentication, audit-log persistence, reporting exports, and Scope 3 are not yet implemented.

References:
- [GHG Protocol — How do I calculate emissions?](https://ghgptechassistance.zendesk.com/hc/en-us/articles/37790958151700-How-do-I-calculate-emissions)
- [GHG Protocol — Standards and Guidance](https://ghgprotocol.org/standards-guidance)

## MVP roadmap

1. Organization workspace and authentication
2. Activity data entry and persistence
3. Verified Mongolia-relevant emission-factor library with provenance and versioning
4. Scope 1 and Scope 2 calculation and reporting methods
5. Audit trail and PDF/Excel exports
6. Scope 3 and expanded ESG disclosures
