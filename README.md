# Carbon ESG

Mongolian-first ESG and greenhouse-gas accounting platform.

## Initial architecture

- `apps/web`: Next.js + TypeScript web application
- `apps/api`: Python FastAPI service
- PostgreSQL planned for multi-tenant data storage
- Emissions calculations are deterministic: activity data × versioned emission factor.
- AI may assist with document extraction and report narratives, but must never invent emission factors or authoritative calculation results.

## MVP milestones

1. Organization workspace and authentication
2. Activity records for fuel and purchased electricity
3. Auditable Scope 1 and Scope 2 calculations
4. Emission-factor source, unit, year, and version tracking
5. Dashboard and PDF/Excel reporting

Scope 3 and expanded ESG disclosures are planned for later milestones.

## Local development

### API
```bash
cd apps/api
python -m venv .venv
# Activate the virtual environment, then:
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Web
```bash
cd apps/web
npm install
npm run dev
```

The API health endpoint is available at `/health`.

## Status

Project foundation only. Authentication, database persistence, validated emission factors, and production deployment are not implemented yet.
