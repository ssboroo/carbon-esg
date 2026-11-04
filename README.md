# Carbon ESG

Mongolian-first ESG and greenhouse-gas accounting platform.

## Project structure

- `apps/web`: Next.js + TypeScript dashboard
- `apps/api`: FastAPI calculation API
- `DEPLOYMENT.md`: container build instructions and production-readiness checklist

## Current functionality

- Premium responsive Mongolian-language dashboard.
- Activity form for Scope 1 and Scope 2 records.
- API-backed deterministic CO2e calculation.
- Explicit emission-factor source, HTTPS URL, year, unit, and version on each calculation record.
- CSV export of the records held in the current browser page session.
- API health endpoint and HTTP/unit tests.
- Dockerfiles for the web and API services.
- GitHub Actions checks for API tests, web type-check, and web production build.

## Local development

### API

```bash
cd apps/api
python -m venv .venv
# Activate the virtual environment, then:
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Run API tests:

```bash
cd apps/api
pytest -q
```

### Web

```bash
cd apps/web
cp .env.example .env.local
npm install
npm run dev
```

Set `NEXT_PUBLIC_API_URL` to the API origin. The browser calls `POST /v1/calculations`.

## Accounting safeguards

- The API does not bundle or invent emission factors.
- Every calculation record must provide a factor value, matching activity unit, source name, HTTPS source URL, year, and version.
- The factor is interpreted as kgCO2e per activity unit.
- AI is not used as the authoritative calculator.
- The current implementation is a calculation prototype, not a verified corporate inventory.

Scope 2 reporting may require location-based and market-based totals depending on the applicable market and contractual-instrument criteria. See the [GHG Protocol Scope 2 Guidance](https://ghgprotocol.org/scope-2-guidance).

## Important production limitations

**Do not use this version to store real customer or confidential business data yet.** The calculation endpoint is stateless; dashboard records exist only in browser memory. PostgreSQL persistence, authentication, tenant isolation, durable audit logs, verified Mongolia-specific emission factors, complete Scope 2 dual reporting, backups, and production monitoring remain to be implemented and tested.

See [DEPLOYMENT.md](DEPLOYMENT.md) for the release checklist.
