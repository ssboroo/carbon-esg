# Production readiness audit — 2026-11-04

## Current decision

**NOT APPROVED FOR PRODUCTION CUSTOMER DATA.** This repository is an engineering foundation and prototype. A green CI run does not establish security, legal compliance, accounting assurance, availability, or production readiness.

## Verified in CI

- Next.js dependency audit (production dependencies), TypeScript type check and production build.
- Python API tests.
- PostgreSQL 16 migration execution.
- Schema smoke checks for required tables, forced RLS flags, tenant policies and audit append-only trigger.
- MCP SDK installation and MCP calculation-preview tests.

## Critical blockers (must close before production)

| Priority | Area | Current gap | Required exit evidence |
|---|---|---|---|
| P0 | Identity | No OIDC/OAuth login, MFA or session lifecycle | Auth integration tests, token validation, MFA policy |
| P0 | Authorization | No server-side membership/role checks on API routes | Role matrix tests; deny-by-default tests |
| P0 | Tenant isolation | RLS smoke test only; no restricted runtime DB role or cross-tenant attack tests | Two-tenant integration suite under non-owner, non-superuser role |
| P0 | Persistence | Dashboard records remain browser memory; calculation API is stateless | Activity/factor/snapshot transaction integration tests |
| P0 | Secrets | No managed production secret integration | Secret rotation evidence; no secrets in images/logs |
| P0 | Evidence | No private object storage, malware scan or upload validation | Upload threat tests, encryption, retention and access tests |
| P0 | Backups | No backup/restore procedure tested | Successful restore drill with RPO/RTO evidence |
| P0 | Deployment | No staging or production environment, domain or TLS evidence | Staging smoke tests, TLS and rollback evidence |
| P0 | Accounting | Scope 3, Scope 2 dual reporting and factor governance incomplete | GHG technical review and golden calculation tests |
| P0 | Legal | Registry seed is only a discovery index; full legal texts/statuses not all verified | Mongolian legal reviewer sign-off and versioned official source evidence |
| P1 | Audit | Append-only table trigger exists, but business events are not comprehensively written | End-to-end audit event assertions for every mutation |
| P1 | Monitoring | No metrics, error tracking, alert routing or incident runbook | Alert test, dashboard and incident exercise |
| P1 | Resilience | No rate limits, request size limits or tested retry/idempotency | Abuse tests and load tests |
| P1 | MCP | Local stdio preview only; no remote OAuth/tenant binding | Remote auth, consent, tenant tests and MCP security review |
| P1 | Web | Workspace/profile are demo placeholders; no auth or server-backed data | Authenticated end-to-end tests |
| P1 | CI/CD | No container scanning, SBOM, SAST, E2E or deployment gate | Required CI jobs and protected-branch rules |

## Changes in this hardening branch

- Separate liveness `/health` from readiness `/ready`.
- Readiness fails closed when PostgreSQL is missing/unavailable or migrations are not applied.
- Production startup requires DATABASE_URL and explicit CORS allow-list.
- API docs/OpenAPI are disabled in production by default.
- Adds baseline API security response headers.
- Keeps no auto-migration at application startup: run Alembic as a controlled deployment step.

## Release sequence

1. Identity, tenant authorization, restricted DB role and cross-tenant tests.
2. Persistent activity/factor/snapshot/audit services and authenticated web flows.
3. Evidence storage, scanning, backup/restore and operational controls.
4. Scope 1/2/3 accounting correctness, verified factor governance and legal review.
5. Remote MCP with OAuth, explicit consent and tenant-scoped tools.
6. Staging deployment, security testing, restore drill, load test and rollback.
7. Independent legal/accounting/security sign-off before customer data or public claims.

## Free hosting warning

Free tiers may sleep, throttle, delete ephemeral disks, cap database storage and provide weak backup guarantees. A free tier is suitable for development/demo only unless the selected provider's current terms, persistence, security, data residency and recovery characteristics are verified. Do not promise enterprise availability on a free tier.

## Acceptance rule

Do not mark production-ready based on a checklist being written or CI passing alone. Every P0 item must have implementation, automated tests, operational evidence and named human review. Legal applicability and GHG methodology require qualified human sign-off.
