# Enterprise persistence foundation

This change introduces the first persistent PostgreSQL schema for Carbon ESG.

## Included
- Organizations (tenants), users and tenant memberships with role field.
- Versioned emission-factor records with source provenance, validity and approval state.
- Activity records linked to a specific factor version.
- Evidence metadata with storage key, SHA-256 and malware-scan state.
- Immutable calculation snapshots with methodology/engine versions and input digest.
- Append-only audit events protected by a PostgreSQL trigger.
- PostgreSQL row-level security (RLS) policies for tenant-owned tables.

## Required security integration before customer use
1. Authenticate users with a trusted OIDC provider; never trust user/tenant IDs in request bodies.
2. Resolve membership and role server-side for every request.
3. Set `app.current_tenant_id` from the authorized membership inside each transaction using `set_tenant_context`.
4. Use a non-owner, non-superuser database role for the application. Table owners and superusers can bypass RLS unless deployment roles are configured correctly.
5. Add authorization tests proving tenant A cannot read/write tenant B data.
6. Store uploaded files in private object storage; validate type/size, scan for malware, and verify SHA-256 before marking evidence accepted.
7. Add backup/restore tests, retention policy and legal hold before production.

## Migration
Install dependencies and run:
```bash
alembic upgrade head
```

Set `DATABASE_URL=postgresql+psycopg://...` in the API environment. Do not put credentials in source control.

## Limitations
This is a schema and database-session foundation, not a complete authentication or evidence-upload feature. API routes are not yet switched to persistent storage. The initial migration and RLS behavior must be tested against a real PostgreSQL instance and a restricted application role before any production claim.
