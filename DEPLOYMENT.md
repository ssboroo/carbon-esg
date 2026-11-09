# CARBON ESG — deployment guide

## Architecture

- Frontend: Next.js App Router on a Render Node web service.
- API: FastAPI on a Render Python web service.
- Database: Neon PostgreSQL (AWS Singapore).
- Authentication: Neon Managed Better Auth. The Next.js server proxies auth requests on the same origin so browser sessions do not depend on third-party cookies.
- API authentication: EdDSA JWT verification against the configured Neon JWKS endpoint.
- Evidence files: private S3-compatible object storage plus a reachable ClamAV daemon. Evidence upload is unavailable until both are configured.

## Current release state

The repository contains authenticated organization workspaces, tenant-scoped inventory and activity APIs, verified-factor review, Scope 1/2 calculations, audit snapshots, and the Evidence Vault API/UI.

This is an integration-ready preview candidate, **not a verified production deployment**. The GitHub repository does not prove that Render services are live, that Neon has been migrated, that trusted domains are configured, or that S3/ClamAV are reachable. Do not enter customer or confidential data until the staging checklist below passes.

## Render Blueprint

The Blueprint is in render.yaml. Open:

https://dashboard.render.com/blueprint/new?repo=https://github.com/ssboroo/carbon-esg

Review the two services before applying. The frontend is a Node web service (not a static site) because it hosts the same-origin Managed Auth proxy and protected server-rendered workspace.

The Blueprint requests free plans for an MVP preview. Free services can sleep after inactivity and may cold-start; they do not provide a production SLA. Confirm the current plan, region, and pricing in the Render dashboard before creating services.

## Neon configuration

The Neon project is configured for AWS Singapore and Managed Better Auth. The public Auth base URL and JWKS URL are in the Blueprint; these are public metadata, not secrets.

- Create or select a dedicated **isolated development branch** for the preview. Do not point a preview at the default/shared production branch.
- Runtime DB URL: use the pooled connection string with a restricted carbon_esg_app role, stored only in the API service as DATABASE_URL.
- The runtime role must have rolsuper=false and rolbypassrls=false. Never use neondb_owner as the API runtime role.
- Migration DB URL: use the direct/unpooled connection string with a dedicated migration credential, only in a secure migration environment as DATABASE_URL_UNPOOLED. Do not add it to the public web service or API runtime environment.
- The versioned Alembic chain is 0001 through 0006 (current head: 0006_factor_geo_validity). Review the generated SQL before applying it to the isolated branch. The new migration preserves unknown legacy factor validity as NULL and marks its geography LEGACY_UNSPECIFIED; it does not infer validity from factor_year.
- Never commit either connection string or the cookie secret.

The API intentionally allows health checks without a configured database. Database-backed organization, inventory, calculation, review, and evidence routes will not be usable until their required services are configured.

## Staging migration procedure

1. Confirm the target Neon branch is the isolated development branch.
2. Confirm the migration credential is allowed to create/alter the intended schema objects.
3. In a secure terminal or CI secret context, run:

   ~~~bash
   cd apps/api
   DATABASE_URL_UNPOOLED="<Neon direct/unpooled migration URL>" alembic upgrade head
   ~~~

4. Verify alembic current reports 0006_factor_geo_validity.
5. Configure the API DATABASE_URL with the pooled restricted runtime role, not the migration credential.
6. Verify the runtime role has rolsuper=false and rolbypassrls=false.
7. Run the tenant-isolation smoke tests with two separate test users and organizations before entering real information.

Do not run the migration against the shared/default Neon branch until the isolated staging run and backup/recovery plan are reviewed.

## Render environment variables

The Blueprint sets the public Auth URLs and generates the server-only NEON_AUTH_COOKIE_SECRET for the web service. Set the following manually in the correct service secret stores:

- API: DATABASE_URL (pooled, restricted runtime role), CORS_ORIGINS (exact web origin).
- Web: confirm NEON_AUTH_BASE_URL, NEON_AUTH_COOKIE_SECRET, and NEXT_PUBLIC_API_URL (public API origin).

After Render provisions the web URL, add the exact HTTPS frontend origin to Neon Auth trusted domains. Never expose DATABASE_URL, DATABASE_URL_UNPOOLED, S3 credentials, or the cookie secret to browser variables or Git.

## Evidence Vault requirements

The Evidence Vault fails closed by design. Uploads require all of the following:

- Private S3-compatible bucket and server-side encryption.
- API-only S3 endpoint, region, bucket, access key and secret key.
- Reachable private ClamAV daemon (CLAMAV_HOST, CLAMAV_PORT).
- Production object-storage endpoint using HTTPS.

These settings are not provisioned automatically by the current Render Blueprint. Until they are configured and tested, evidence upload/download is not part of the working preview. Do not disable malware scanning to make uploads succeed.

## Local development

API:

~~~bash
cd apps/api
python -m venv .venv
# activate the virtual environment
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
~~~

Web:

~~~bash
cd apps/web
npm install
# Set NEON_AUTH_BASE_URL, NEON_AUTH_COOKIE_SECRET (32+ chars),
# and NEXT_PUBLIC_API_URL in .env.local
npm run dev
~~~

Localhost origins are pre-approved by Neon Auth. For a hosted preview, add the exact HTTPS Render frontend origin to the Neon Auth trusted-domain allowlist.

## Preview acceptance checklist

- [ ] Render API and web services deploy and pass their health checks.
- [ ] Neon Auth sign-up/sign-in works from the hosted web origin.
- [ ] User A can create and list their organization.
- [ ] User B cannot list or access User A's organization or records.
- [ ] A user can create an inventory and add activities only using an approved, sourced factor.
- [ ] Each new factor records geography code/name/boundary and explicit applicability dates; those dates cover the entire reporting period.
- [ ] Each activity records its actual geography; a non-global factor code exactly matches that activity geography.
- [ ] Calculation snapshots retain the factor version, source, geography, applicability interval, method, and exact input values.
- [ ] Scope 2 location-based and market-based totals remain separate; they are never added together.
- [ ] A second owner/admin can review a factor; the submitter cannot approve their own submission.
- [ ] Evidence upload rejects unsupported files and rejects uploads when ClamAV is unavailable.
- [ ] If evidence storage is enabled, uploaded files remain private and authorized download links expire after five minutes.
- [ ] Logs and audit records contain no credentials or raw file contents.

## Production limitations

Before customer production use, complete a security review, rate limiting, monitoring/alerting, backup and restore drills, retention/deletion policy, custom email delivery review, data-processing/privacy terms, and accounting/legal review of the applicable Mongolian and international reporting requirements. The current CO2e-only factor model does not yet provide the gas-level, biogenic-emissions, base-year, or comparative-period disclosures required by GRI 102: Climate Change 2025. Render/Neon free tiers are suitable only for a limited preview, not a production SLA.
