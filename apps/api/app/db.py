"""Database primitives. Request handlers must set tenant context before querying RLS tables."""
import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def _database_url() -> str:
    value = os.getenv("DATABASE_URL", "").strip()
    if not value:
        raise RuntimeError("DATABASE_URL is required for database operations")
    # psycopg v3 is used explicitly; accept Neon postgres:// and postgresql:// URLs.
    if value.startswith("postgres://"):
        value = value.replace("postgres://", "postgresql+psycopg://", 1)
    elif value.startswith("postgresql://"):
        value = value.replace("postgresql://", "postgresql+psycopg://", 1)
    return value


def build_engine():
    return create_engine(
        _database_url(),
        pool_pre_ping=True,
        pool_size=3,
        max_overflow=2,
        pool_recycle=300,
    )


def build_session_factory(engine=None):
    return sessionmaker(
        bind=engine or build_engine(),
        autoflush=False,
        expire_on_commit=False,
    )


def set_tenant_context(session, organization_id: str) -> None:
    """Set transaction-local RLS context; call inside an active transaction."""
    session.execute(
        __import__("sqlalchemy").text(
            "SELECT set_config('app.current_organization_id', :organization_id, true)"
        ),
        {"organization_id": str(organization_id)},
    )
