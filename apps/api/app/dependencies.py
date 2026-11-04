"""FastAPI dependencies for database sessions and identity-scoped access."""
from collections.abc import Generator

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from .db import build_session_factory


def get_db_session() -> Generator[Session, None, None]:
    try:
        session = build_session_factory()()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not configured",
        ) from exc

    try:
        yield session
    finally:
        session.close()
