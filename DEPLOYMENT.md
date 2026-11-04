# Deployment foundation

This repository now contains multi-stage Dockerfiles for the Next.js web app and FastAPI API.

## Web container

Build from the web app directory:

```bash
cd apps/web
docker build --build-arg NEXT_PUBLIC_API_URL=https://api.example.com -t carbon-esg-web .
docker run --rm -p 3000:3000 carbon-esg-web
```

The API URL is a public browser-side endpoint and is embedded during the web build. Never put credentials, database URLs, signing keys, or private tokens in `NEXT_PUBLIC_*` variables.

## API container

Build from the API directory:

```bash
cd apps/api
docker build -t carbon-esg-api .
docker run --rm -p 8000:8000 -e CORS_ORIGINS=https://app.example.com carbon-esg-api
```

Configure `CORS_ORIGINS` as a comma-separated allow-list of exact trusted web origins. Do not use a wildcard.

## Current release blockers

This is a deployment foundation, not yet a production-ready multi-customer SaaS. Before accepting real customer data or making public ESG claims, implement and verify:

1. PostgreSQL persistence and versioned database migrations.
2. Authentication, organization membership, and tenant isolation enforced in every data query.
3. Persistent audit events and immutable calculation snapshots.
4. A reviewed Mongolia-specific emission-factor library with source, geography, year, unit, gases/GWP basis, and version metadata.
5. Scope 2 location-based and market-based reporting logic, including applicable contractual-instrument quality checks.
6. Backups, restore drills, monitoring, rate limiting, dependency/security scanning, and operational alerts.
7. End-to-end tests and a real deployment with TLS, secrets management, and configured production origins.

Until persistence is implemented, calculations are stateless. The current browser dashboard keeps its displayed records only in page memory and does not save them to a server or database.
