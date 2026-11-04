"""PostgreSQL connection and request-scoped tenant context helpers.

The caller must authenticate the user and authorize organization membership before
setting a tenant context. Never accept tenant IDs directly from an untrusted client.
"""
from collections.abc import Generator
import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
) if DATABASE_URL else None

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False) if engine else None


def get_db() -> Generator[Session, None, None]:
    """Yield a database session; fail closed when DATABASE_URL is not configured."""
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is required for persistent API operations")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def set_tenant_context(db: Session, tenant_id: str) -> None:
    """Set PostgreSQL RLS context for this transaction/session.

    tenant_id must come from a server-side authorization decision, not request JSON.
    set_config(..., true) scopes the value to the current transaction.
    """
    db.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
        {"tenant_id": tenant_id},
    )
