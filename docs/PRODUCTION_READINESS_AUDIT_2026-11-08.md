# CARBON ESG — Production Readiness Audit

**Audit date:** 2026-11-08  
**Repository:** `ssboroo/carbon-esg`  
**Default branch reviewed:** `main`  
**Purpose:** Distinguish code present on the default branch, work available only in pull requests, infrastructure actually provisioned, and evidence still required before customer production use.

## Executive verdict

**Not production-ready.** The default branch is a stateless Scope 1/2 calculation prototype with a deployment blueprint, not a deployed multi-tenant SaaS. Significant backend, authentication, persistence, workspace, and factor-review work exists in open pull requests, but it has not been integrated into `main`. The linked Render workspace currently has no Carbon ESG service. A Neon project named `carbon-esg` exists, but the default Neon branch does not contain the application tables.

Do not onboard customers or store customer ESG data until the P0 release gates below are completed and independently verified.

## Evidence reviewed

- Repository metadata: public repository, default branch `main`.
- Latest default-branch commit: `2c90f85462124dcf2e313f2a82b1e3db8c36d003` (2026-11-04).
- `README.md`, `DEPLOYMENT.md`, `render.yaml`, API entrypoint, Python requirements, web package manifest, and GitHub Actions workflows.
- Pull requests #16–#25, including their base/head branches, states, descriptions, and available CI runs.
- Linked Render workspace service inventory.
- Neon project `carbon-esg`, its branches, public table inventory, RLS flags/policies, and database roles. SQL inspection was read-only.

## Current default-branch state

The README explicitly describes PostgreSQL persistence as planned and the current calculation endpoint as stateless. The API currently exposes:
- `GET /health`
- `POST /v1/calculations`

The calculation request supplies activity data and emission-factor values. The API validates provenance fields and calculates deterministically, but the default-branch endpoint does not persist inventories or calculation history. The README also identifies Scope 2 market/location-based distinction, authentication, durable audit logs, reporting exports, and Scope 3 as not yet implemented on `main`.

The Render Blueprint is explicitly a free MVP preview. It defines a free API web service and a static frontend, and its comments/documentation warn that the free API sleeps after inactivity and is not suitable for confidential customer production data.

## Pull-request integration status

The following work is present in open PRs, not in the default branch:

| PR | Work | State at audit | Dependency / limitation |
|---|---|---|---|
| #20 | Tenant-safe PostgreSQL schema, RLS, immutable factor versions | Open, non-draft | Starts from `main`; shared Neon main not migrated |
| #21 | Neon Managed Auth and protected API | Open, non-draft | Based on #20; production trusted domain/cookie configuration remains |
| #22 | RLS-protected organization workspace API | Open, non-draft | Based on #21; shared migration and deployed role checks remain |
| #23 | Persist inventories and auditable Scope 1/2 calculations | Open, non-draft | Based on #22; Scope 2 dual reporting and factor administration still limited |
| #24 | Mongolian workspace UI connected to persisted APIs | Open, draft | Based on #23 |
| #25 | Tenant-scoped emission-factor submission/review API | Open, draft | Based on #24; four-eyes review is not enforced |
| #16 | Private Evidence Vault API and malware scanning | Open, draft | Separate older dependency chain; needs private object storage and ClamAV |
| #17 | Evidence Vault web UI | Open, draft | Based on #16 |
| #18 | API HTTP contract tests | Open, draft; GitHub reports not mergeable | Separate branch from `main` |

Available GitHub Actions runs for the latest #23, #24, and #25 head commits completed successfully for the workflows shown. That is useful CI evidence, but it is not proof of production deployment, migration safety, full accounting correctness, or security assurance. The combined commit-status endpoint returned no status entries for the sampled PR heads.

**Integration warning:** PRs #20 → #21 → #22 → #23 → #24 → #25 form a dependency chain. Review and integrate in order; do not merge a later stacked PR directly into `main`. PRs #16/#17 and #18 are separate workstreams and should not be merged blindly into the new architecture.

## Infrastructure findings

### Render
The linked Render workspace was inspected. It currently lists two unrelated services (`qr-menu-api` and `bot`); no `carbon-esg-api` or `carbon-esg-web` service was found. Therefore a live Carbon ESG deployment was not verified.

### Neon
A Neon project named `carbon-esg` exists in AWS Singapore.

- The default `main` branch is ready but its application schema is absent: the inspected non-system tables are in `neon_auth`; no Carbon ESG `public` application tables were found.
- A separate non-default branch named `mcp-migration-2026-11-04T12-42-17` contains seven application tables: organizations, memberships, emission factors, inventories, activity records, calculation runs, and audit events.
- Those seven tables have RLS enabled and forced, with tenant policies present.
- A restricted `carbon_esg_app` role exists on that branch with `rolsuper=false` and `rolbypassrls=false`.
- `neondb_owner` has `rolbypassrls=true`; it must not be used as the API runtime role.
- The inspected isolated branch contains test/development records (3 organizations, 3 memberships, 1 factor, 1 inventory, 1 audit event; no activity records or calculation runs). Do not treat this as customer production data.

No migration was applied to the default Neon branch during this audit.

## Production blockers

### P0 — required before customer data
1. Integrate and review the tenant/auth/API PR chain in dependency order.
2. Validate all migrations against an isolated Neon branch, then apply to the intended production branch with a reviewed rollback/restore plan.
3. Configure Render (or another production host) with the correct frontend and API services; do not use a sleeping free instance for customer production.
4. Set API `DATABASE_URL` to the restricted `carbon_esg_app` role; keep owner/migration credentials separate and secret.
5. Verify Neon Auth issuer, audience, JWKS, trusted frontend domains, cookie secret, exact CORS origins, and end-to-end sign-in on desktop and mobile.
6. Prove tenant isolation using the actual deployed runtime role and cross-tenant negative tests.
7. Run backup and restore drills; verify monitoring, alerting, rate limits, request-size limits, secret handling, and incident recovery.
8. Obtain independent security review and accounting-methodology review before representing results as assurance-ready.

### P1 — required for a credible ESG MVP
1. Complete a controlled, versioned, source-cited Mongolian-relevant emission-factor library; no factor should be invented or silently defaulted.
2. Implement Scope 2 location-based and market-based methods separately and prevent adding alternative method totals together.
3. Add data-quality states, evidence linkage, reviewer decisions, correction/versioning, and a genuine separation-of-duties workflow.
4. Complete PDF/XLSX exports with calculation snapshots, factor provenance, reporting boundary, methodology version, and review status.
5. Add user/member invitations, role administration, MFA policy, and account lifecycle controls.
6. Exercise private Evidence Vault with real private object storage, real ClamAV, backup/restore, and retention controls before enabling uploads.

### P2 — full product scope
1. Implement Scope 3 categories with documented calculation methods and data-quality controls.
2. Build GRI and IFRS/ISSB disclosure mapping as versioned reporting frameworks, not just labels or static templates.
3. Add evidence extraction/OCR and AI-assisted narratives with human approval; AI must never invent factors or authoritative calculation results.
4. Add organization-level ESG metrics, dashboards, year-over-year comparisons, supplier data collection, and controlled exports.
5. Add accessibility, localization, performance, and load testing.

## Release acceptance checklist

A production release should not be approved until all are true:

- [ ] Required PRs integrated and the final main-branch CI is green.
- [ ] Production Neon main contains reviewed application migrations.
- [ ] API connects using the non-owner, non-BYPASSRLS runtime role.
- [ ] Authentication and tenant isolation pass end-to-end negative tests.
- [ ] Production frontend and API are deployed and HTTPS health/readiness checks pass.
- [ ] Emission-factor sources, geography, year, version, units, and approvals are auditable.
- [ ] Scope 2 methods are handled correctly; unsupported Scope 3 claims are excluded.
- [ ] Backups, restore, monitoring, alerting, rate limiting, and security review are complete.
- [ ] Accounting/legal review approves the customer-facing methodology and claims.

## Bottom line

The project has meaningful engineering progress, especially in the unmerged PR stack and isolated Neon branch. However, the default branch and linked infrastructure do not yet form a working production SaaS. Treat the current state as an advanced development/MVP foundation, not a production release.
