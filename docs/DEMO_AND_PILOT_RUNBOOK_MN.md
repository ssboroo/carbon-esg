# CARBON ESG — MVP demo and pilot runbook

**Document status:** operational guide for the current repository state, not a production approval.

This runbook distinguishes what is available on the default branch from work that remains in unmerged pull requests. Do not present a planned feature as deployed functionality.

## 1. Current release truth

The repository default branch is `main`. Its current README and API source describe an early stateless calculator:

- Next.js landing page with static MVP messaging.
- FastAPI `GET /health`.
- FastAPI `POST /v1/calculations` for deterministic Scope 1/2 arithmetic from request-supplied activity data and explicitly sourced factor details.
- No hard-coded emission-factor library.
- No database persistence, authenticated tenant workspace, review workflow or durable audit history on `main`.

The organization workspace, Neon Auth, tenant/RLS persistence, emission-factor review workflow and related UI exist in open feature PRs, not in the deployed default-branch release. They must be reviewed, tested and merged in dependency order before they can be treated as a single integrated application.

**Never describe the current `main` deployment as a production ESG accounting platform.** It is a demonstration of the initial calculation API and landing page.

## 2. Free preview deployment

The root `render.yaml` defines a free Render API web service and static frontend. Render Free services can sleep when idle; the first request after inactivity may take around a minute. This is acceptable for a demonstration, not for an availability commitment to customers.

1. Push/merge the reviewed deployment configuration to the intended deployment branch.
2. In Render, choose **New → Blueprint**, connect `ssboroo/carbon-esg`, and select `render.yaml`.
3. Confirm both services are on the Free plan:
   - `carbon-esg-api` (Python/FastAPI)
   - `carbon-esg-web` (static frontend)
4. Wait for both deployments to finish.
5. Open the API's `/health` endpoint. It must return HTTP 200 and JSON with `status: ok`.
6. Open the frontend HTTPS URL. Check browser developer tools for failed requests and CORS errors.
7. If the generated hostnames differ from the Blueprint wiring, set API `CORS_ORIGINS` to the exact frontend origin and frontend `NEXT_PUBLIC_API_URL` to the API origin, then redeploy.

Use the Render-provided `onrender.com` subdomains for a zero-cost preview. A custom domain is optional and may cost money; do not purchase one for the demo.

## 3. Local development

### API

```bash
cd apps/api
python -m venv .venv
# Activate .venv for your operating system
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

Check liveness:

```bash
curl -i http://localhost:8000/health
```

Expected: HTTP 200, with `{"status":"ok","service":"carbon-esg-api"}`.

Interactive API docs are available at `http://localhost:8000/docs` in the development environment.

### Frontend

In a second terminal:

```bash
cd apps/web
cp .env.example .env.local
# Keep NEXT_PUBLIC_API_URL=http://localhost:8000 for local API
npm install
npm run dev
```

Open `http://localhost:3000`.

### Automated checks

```bash
# API
cd apps/api
pytest -q

# Frontend (separate terminal)
cd apps/web
npm run typecheck
npm run build
```

Only report checks as passed when they have actually completed successfully in the environment being used.

## 4. Calculation demonstration

Use only a factor whose source, URL, publication year, geography, unit, version and applicability have been independently checked for the chosen reporting period.

1. Open the API docs and inspect `POST /v1/calculations`.
2. Prepare a request with a reporting-period start/end and one or more activity records.
3. For every record provide its scope/category, activity amount/unit, factor value and denominator unit, source name, HTTPS source URL, factor year and version.
4. Ensure the activity unit exactly matches the factor denominator unit.
5. Submit the request and inspect the returned Scope 1, Scope 2 and total kgCO2e/tCO2e.
6. Independently reproduce each line as activity quantity × factor value, using the same units and rounding.
7. Save the request and response as demonstration evidence only if the factor license and data handling permit it.

Do not use illustrative values from old README examples for actual reporting. Do not present user-supplied factors as platform-verified. The stateless calculator validates structure and arithmetic; it does not independently certify the source or approval status of a factor.

## 5. Suggested 8-minute product walkthrough

1. **1 min — Problem and scope:** explain Mongolia-first ESG/carbon accounting and the MVP boundary.
2. **1 min — Method:** explain activity data × documented emission factor.
3. **2 min — Evidence:** show the source URL, year, unit and version for the chosen factor.
4. **2 min — Calculation:** submit a small, real and independently checked activity record; explain kgCO2e and tCO2e.
5. **1 min — Limitations:** explain why the current main-branch calculator is stateless and why the result is not an assured inventory.
6. **1 min — Roadmap:** show the pending organization workspace, factor-review workflow, persistence and Scope 2 method distinction as unmerged development work.

## 6. Data and security rules for a demo

- Use synthetic organization names and non-confidential activity quantities unless the relevant privacy/security controls have been reviewed.
- Never paste API keys, database URLs, auth secrets or personal data into GitHub, chat, screenshots or public demo recordings.
- Never connect the current stateless main-branch demo to a customer database or claim tenant isolation.
- Do not create or seed fake Mongolian emission factors. Use a clearly identified, independently verified source or do not demonstrate a numeric result.
- AI-generated factor values are prohibited as calculation inputs.
- A demo result is not a regulatory filing, assurance statement or GHG Protocol conformity claim.

## 7. Go-live gates before real customer onboarding

The following are release blockers, not optional polish:

- Merge and verify the authentication, organization membership, RLS persistence, inventory API, factor-review API and frontend PR dependency chain.
- Apply migrations to an isolated PostgreSQL/Neon branch first; test with a non-owner, non-BYPASSRLS runtime role.
- Verify tenant isolation on every read/write endpoint and every related table.
- Complete Scope 2 location-based/market-based method selection, factor compatibility and separate reporting; never add the two alternative totals together.
- Establish a reviewed Mongolia-relevant factor catalog with primary sources, geography, period, units, version and approval evidence.
- Complete evidence retention, backup/restore, monitoring, rate limiting, incident handling and security review.
- Test a full signup → organization → inventory → factor submission → independent review → activity entry → calculation → audit evidence journey in a staging environment.
- Obtain appropriate accounting/legal review before marketing standards or regulatory compliance claims.

## 8. Zero-budget constraint

The documented preview path uses Render Free and does not require a custom domain or paid add-ons. Free services have resource, sleep and availability limits. Neon Free database should only be connected after the persistence branch has been validated; do not create a paid compute or storage dependency. If a provider changes its free-tier terms, stop and re-check the current official pricing before provisioning.

## 9. Official references to re-check before release

- Render Blueprint specification: https://render.com/docs/blueprint-spec
- Render free instance types: https://render.com/docs/free
- Neon pricing: https://neon.com/pricing
- GHG Protocol standards and guidance: https://ghgprotocol.org/standards-guidance
- GHG Protocol Scope 2 Guidance: https://ghgprotocol.org/scope-2-guidance

Provider free-tier terms and GHG Protocol guidance may change. Re-check these official sources at the time of deployment and before finalizing accounting behavior.
