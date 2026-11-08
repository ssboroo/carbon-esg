"""Database primitives. Set identity and tenant context inside each transaction."""
import os
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def normalize_database_url(value: str) -> str:
    value = value.strip()
    if value.startswith("postgres://"):
        return value.replace("postgres://", "postgresql+psycopg://", 1)
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+psycopg://", 1)
    return value


def build_engine():
    value = normalize_database_url(os.getenv("DATABASE_URL", ""))
    if not value:
        raise RuntimeError("DATABASE_URL is required for database operations")
    return create_engine(
        value,
        pool_pre_ping=True,
        pool_size=3,
        max_overflow=2,
        pool_recycle=300,
    )


@lru_cache(maxsize=1)
def get_engine():
    return build_engine()


def build_session_factory(engine=None):
    return sessionmaker(
        bind=engine or get_engine(),
        autoflush=False,
        expire_on_commit=False,
    )


def set_identity_context(session, user_subject: str) -> None:
    """Expose only a verified identity-provider subject to membership RLS."""
    session.execute(
        text("SELECT set_config('app.current_user_subject', :subject, true)"),
        {"subject": user_subject},
    )


def set_tenant_context(session, organization_id: str) -> None:
    """Set transaction-local RLS context only after membership is established."""
    session.execute(
        text("SELECT set_config('app.current_organization_id', :organization_id, true)"),
        {"organization_id": str(organization_id)},
    )
