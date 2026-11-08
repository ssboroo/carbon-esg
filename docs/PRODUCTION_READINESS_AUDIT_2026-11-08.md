# CARBON ESG — Production Readiness Audit

**Audit date:** 2026-11-08  
**Repository:** `ssboroo/carbon-esg`  
**Main commit reviewed:** `62ac209632a988fbcbdef0b2d2a2cfe15583af0c`

## Executive verdict

<badge>Advanced MVP codebase — not production-ready</badge>

The default branch now contains a meaningful multi-tenant ESG accounting MVP foundation: Neon Auth integration, PostgreSQL tenant schema and RLS, organization workspace, persisted inventories and calculation snapshots, human-reviewed emission factors, Mongolian workspace UI, Evidence Vault API/UI, CSV export, and separate Scope 2 location-based/market-based results.

However, **there is still no verified live Carbon ESG deployment and no application schema on the default Neon branch**. Production credentials, database migrations, trusted auth domains, private evidence storage, ClamAV, backup/restore, monitoring and independent security/accounting reviews are not complete. Do not onboard customers or store real ESG evidence yet.

## What is present on main

| Area | Integrated capability | Remaining limitation |
|---|---|---|
| Authentication | Neon Managed Auth sign-up/sign-in integration; FastAPI EdDSA JWT/JWKS verification | Production trusted origin, cookie and end-to-end device testing not verified |
| Tenant security | PostgreSQL tenant schema, transaction-local identity/tenant context, forced RLS, tenant-aware foreign keys | Must validate on the intended DB using the actual restricted runtime role |
| Organizations | Create/list organization; initial owner membership; audit event | Invitations, member management and full account lifecycle not complete |
| Inventories | Reporting-period inventory and activity records persisted | Workflow approvals, reporting boundaries and richer data quality controls remain |
| Factors | Provenance-rich factor submission, independent owner/admin review, four-eyes rule | Official Mongolian factor library is not seeded; values must be source-verified by humans |
| Calculations | Decimal arithmetic, immutable factor snapshots, append-only calculation history and audit events | No independent assurance or full standards-conformity claim |
| Scope 2 | Explicit location-based and market-based factor/activity basis; separate alternative totals; inventory primary method | GRI 102:2025 gas/biogenic/base-year/comparative disclosures remain incomplete |
| Workspace | Mongolian organization, inventory, factor registry and review UI | Full accessibility, localization and user administration still needed |
| Evidence Vault | Authenticated tenant upload/list/download API and UI; file signature checks; fail-closed malware scanning; immutable metadata | S3-compatible private bucket and ClamAV are not configured; upload is expected to return 503 until provisioned |
| Export | CSV includes activity, factor version, source, year, method and calculation metadata | Not a complete GRI/IFRS report, PDF assurance pack or XBRL export |
| CI | API tests, offline Alembic SQL validation, TypeScript and Next.js production build workflows | CI does not prove a live database migration, real auth session or production deployment |

## Git integration

The main branch includes the staged integration work from PRs #20, #30–#36, #39–#42. The old stacked PRs #21–#25, #27–#29 and #37 were closed after their functionality was ported to clean branches and integrated.

Older PRs #2–#19 remain a separate legacy stack. They include overlapping OIDC/database/UI implementations and must not be merged blindly into the current Neon Auth architecture. Review useful isolated items (e.g. MCP or legal-registry material) individually before porting.

## Infrastructure verification

### Render

- The linked Render workspace currently has no Carbon ESG service running.
- A Render Blueprint named `carbon-esg-preview` has been created with auto-sync disabled.
- The latest plan proposes two free Singapore web services: FastAPI API and Next.js web app.
- The plan requires a manually supplied `DATABASE_URL` for the API service.
- The plan has **not** been approved or applied; no Render services/resources were created by this audit.
- Free instances may sleep and are suitable only for a non-confidential preview, not customer production.

Blueprint review: https://dashboard.render.com/blueprint/exs-dbo3bqjl550s738kitv0/sync/exe-dbo3ioe7bikc73fskuo0

### Neon

- A Neon project for Carbon ESG exists.
- The default `main` branch was inspected read-only and contains Neon Auth/system tables, but no Carbon ESG application tables.
- A separate development branch contains the earlier seven-table tenant schema and a `carbon_esg_app` role with `rolsuper=false` and `rolbypassrls=false`.
- That development branch is not the current full schema: it predates the factor-review, Evidence Vault and Scope 2 dual-method migrations. Its organization discovery policy also predates the corrected membership-based SELECT policy.
- No verified Alembic revision row was found on that development branch.
- `neondb_owner` has RLS bypass privileges and must never be used as the API runtime role.
- No migration was applied to the default Neon `main` branch.

## P0 — blockers before real customer data

1. Create/use a clean isolated Neon staging branch from the intended base and run the complete Alembic chain through the current head.
2. Verify RLS policies, including organization discovery, membership access, factor review, evidence and cross-tenant negative tests.
3. Create separate migration and runtime roles. Runtime role must be non-superuser, non-owner, and `NOBYPASSRLS`; store only its connection string in the API secret store.
4. Test sign-up, sign-in, sign-out, token refresh, trusted origins, cookie secret, CORS and mobile browser behavior against the deployed staging services.
5. Only after staging verification, review and apply migrations to the intended Neon branch with a backup/restore plan.
6. Review the Render Blueprint and manually provide the correct restricted-role `DATABASE_URL`; approve the plan only after its service/env details are reviewed.
7. Run full end-to-end tests with two separate organizations and users using the actual deployed runtime role.
8. Complete backup/restore, monitoring, rate limiting, secret rotation, incident response, retention and independent security review.

## P1 — accounting and evidence readiness

1. Populate a source-verified Mongolian emission-factor library with geography, year, unit, methodology, version and independent approval.
2. Complete GRI 102: Climate Change 2025 gas-level CO2/CH4/N2O, biogenic emissions, GWP version, base-year/recalculation and comparative-period disclosures.
3. Complete GRI/IFRS/ISSB disclosure mapping and Mongolia legal-compliance mapping as versioned, reviewed rules.
4. Provision a private object-storage bucket with restricted credentials, server-side encryption, backup/restore and retention.
5. Provision a private ClamAV scanner reachable only by the API. Keep Evidence Vault uploads disabled/fail-closed until this is live and tested.
6. Produce full PDF/XLSX reporting packs with methodology, boundary, factor provenance, Scope 2 method, review state, evidence references and calculation snapshots.
7. Add data-quality scoring, evidence extraction with human approval, member invitations, role administration and audit review UI.

## P2 — broader product scope

- Scope 3 categories and supplier data collection.
- Full GRI/IFRS/ISSB reporting workflows, XBRL where required.
- AI-assisted narratives and evidence extraction with human review; AI must never invent factors or authoritative calculation outputs.
- Organization dashboards, year-over-year comparisons and portfolio analytics.
- Load, accessibility, penetration and disaster-recovery testing.

## Release acceptance checklist

- [ ] Current Alembic head is applied to an isolated staging branch and validated.
- [ ] RLS isolation passes cross-tenant negative tests with the real runtime role.
- [ ] Production Neon branch has reviewed migrations and separate restricted roles.
- [ ] Render API and web services are live over HTTPS and health checks pass.
- [ ] Neon Auth trusted domains, cookie/session settings and CORS are verified.
- [ ] Emission factors are source-cited, geographically appropriate, versioned and independently reviewed.
- [ ] Location-based and market-based Scope 2 results remain separate.
- [ ] GRI 102:2025 and any claimed IFRS/ISSB mapping are independently reviewed.
- [ ] Evidence storage and malware scanning are live, private and restore-tested before uploads are enabled.
- [ ] CSV/PDF/XLSX outputs, backups, monitoring, retention and incident response are tested.
- [ ] Independent security, accounting and legal review is complete.

## Bottom line

The project is now an integrated MVP codebase, not merely a stateless prototype. The remaining gap is **safe infrastructure activation and complete accounting/reporting coverage**. Code merged to GitHub is not proof of production operation. Until Neon migrations, Render deployment, real auth, tenant isolation, private evidence storage and independent reviews are verified, the correct status remains **development / controlled demo only**.
