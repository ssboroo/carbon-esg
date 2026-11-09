# Carbon ESG

Mongolia-first ESG and greenhouse-gas accounting SaaS. The MVP is built around traceable activity data, explicitly sourced emission factors, deterministic calculations, tenant isolation, and an auditable review trail.

## Current implementation

- Web: Next.js App Router + TypeScript, Mongolian-language workspace.
- API: FastAPI + Pydantic + SQLAlchemy.
- Database: PostgreSQL/Neon schema with Alembic migrations 0001–0006, tenant-scoped foreign keys and row-level security.
- Authentication: Neon Managed Auth; the web app uses a same-origin auth proxy and the API verifies EdDSA JWTs.
- Organizations and inventories: authenticated organization workspaces and reporting periods.
- Emission-factor registry: source name, HTTPS source URL, document reference, data/publication year, unit, version, geography, boundary type, and applicability dates; a second owner/admin performs independent review.
- Activity records: activity amount, unit, actual geography, and a reviewed factor. Units must match exactly.
- Calculations: deterministic Decimal arithmetic for Scope 1 and Scope 2. Scope 2 location-based and market-based totals remain separate; the selected primary method is used for the headline total.
- Auditability: factor/activity provenance is copied into audit events and immutable calculation input snapshots.
- Evidence Vault: tenant-scoped API/UI exists, but file upload is fail-closed until private object storage and ClamAV are configured.
- Export: CSV export includes activity and factor provenance. It is not a full GRI/IFRS report.

This is an integration-ready MVP preview candidate, **not a verified production deployment**. The default Neon branch has not been authorized for migration or customer data. See DEPLOYMENT.md before configuring a preview.

## Factor geography and applicability

Each new factor records a stable geography code and name, boundary type, and inclusive valid-from/valid-to dates. The factor data/publication year is separate from the dates during which the factor applies.

Each activity record stores its actual geography. A non-global factor can only be used when its geography code exactly matches the activity geography code. A factor with code GLOBAL may apply across activity geographies. The factor validity interval must cover the entire inventory reporting period.

The migration preserves missing legacy metadata rather than guessing: legacy factors receive LEGACY_UNSPECIFIED geography and NULL validity dates. They remain available for historical inspection but are excluded from new activity entry and recalculation. factor_year is never treated as proof of validity. See docs/accounting/FACTOR_GEOGRAPHY_AND_APPLICABILITY.md.

## Accounting boundaries and known gaps

- The current factor model accepts kgCO2e factors. It does not yet calculate gas-by-gas CO2, CH4, and N2O components or separate biogenic CO2.
- GRI 102: Climate Change 2025 includes additional requirements such as gas-level Scope 2 breakdown, biogenic emissions, base-year information, and comparative periods. The current MVP is **not GRI 102 compliant**. Check the official standard and effective date before preparing disclosures.
- Scope 3, full market-based contractual-instrument quality criteria, base-year recalculation, assurance workflows, and complete PDF/Excel reporting are not yet implemented.
- No emission factors are hard-coded or AI-generated. No source-verified Mongolia factor library is pre-seeded. Do not use illustrative values for real reporting.
- The stateless POST /v1/calculations endpoint remains available for explicit previews; the persisted organization/inventory workflow is the main MVP path.

## API routes

- GET /health — health check.
- GET /v1/auth/me — protected identity check.
- GET and POST /v1/organizations — list/create organizations for the authenticated subject.
- GET and POST /v1/organizations/{organization_id}/emission-factors — list approved factors / submit a new factor version.
- GET /v1/organizations/{organization_id}/emission-factors/review-queue — owner/admin review queue.
- POST /v1/organizations/{organization_id}/emission-factors/{factor_id}/review — independent approval/rejection.
- GET and POST /v1/organizations/{organization_id}/inventories — list/create reporting periods.
- GET and POST /v1/organizations/{organization_id}/inventories/{inventory_id}/activities — list/add activity records.
- POST /v1/organizations/{organization_id}/inventories/{inventory_id}/calculate — create an immutable calculation snapshot.
- POST /v1/calculations — stateless calculation preview.
- GET /docs — FastAPI API documentation.

Database-backed routes require migrations and a restricted PostgreSQL runtime role. Evidence Vault additionally requires private object storage and malware scanning.

## Local development

### API

~~~bash
cd apps/api
python -m venv .venv
# Activate the virtual environment, then:
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
pytest -q
~~~

### Web

~~~bash
cd apps/web
cp .env.example .env.local
# Set development-only Neon Auth values and NEXT_PUBLIC_API_URL.
npm install
npm run dev
npm run typecheck
npm run build
~~~

Use environment variable names in apps/api/.env.example and apps/web/.env.example. Never commit database URLs, auth secrets, S3 credentials, or tokens.

## Database migration and deployment

Review migrations and apply them only to an isolated development/staging branch first:

~~~bash
cd apps/api
DATABASE_URL_UNPOOLED="<direct Neon migration URL>" alembic upgrade head
alembic current
~~~

Use a pooled connection with a restricted NOSUPERUSER NOBYPASSRLS runtime role for DATABASE_URL; do not run the API as neondb_owner. Never point a preview at the shared/default Neon branch. See DEPLOYMENT.md for the complete staging and go-live gate.

## Official accounting references

- GHG Protocol — Calculation Tools FAQ: https://ghgprotocol.org/calculation-tools-faq
- GHG Protocol — Scope 2 Guidance: https://ghgprotocol.org/scope-2-guidance
- GRI 102: Climate Change 2025: https://www.globalreporting.org/publications/documents/english/gri-102-climate-change-2025/
- GRI Topic Standards for Climate Change and Energy: https://www.globalreporting.org/standards/standards-development/topic-standard-for-climate-change-and-energy/
