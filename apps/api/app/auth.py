"""OIDC bearer-token validation and server-authorized tenant membership.

The API does not issue passwords or trust tenant/role claims from request bodies.
Users must be provisioned and linked to an OIDC (issuer, subject) pair by an
administrator before they can access an organization.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os
from uuid import UUID

import jwt
from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError, PyJWKClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .database import get_db
from .models import Membership, User

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Identity:
    issuer: str
    subject: str
    email: str


@dataclass(frozen=True)
class TenantContext:
    tenant_id: UUID
    user_id: UUID
    role: str


@lru_cache(maxsize=1)
def _jwks_client() -> PyJWKClient:
    jwks_url = os.getenv("OIDC_JWKS_URL", "").strip()
    if not jwks_url.startswith("https://"):
        raise RuntimeError("OIDC_JWKS_URL must be configured as an HTTPS URL")
    return PyJWKClient(jwks_url, cache_keys=True, lifespan=300)


def verify_access_token(token: str) -> Identity:
    issuer = os.getenv("OIDC_ISSUER", "").strip()
    audience = os.getenv("OIDC_AUDIENCE", "").strip()
    if not issuer or not audience:
        raise RuntimeError("OIDC_ISSUER and OIDC_AUDIENCE must be configured")
    signing_key = _jwks_client().get_signing_key_from_jwt(token)
    claims = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=audience,
        issuer=issuer,
        options={"require": ["exp", "iat", "sub", "iss", "aud"]},
        leeway=30,
    )
    if claims.get("email_verified") is not True:
        raise InvalidTokenError("A verified email claim is required")
    email = claims.get("email")
    subject = claims.get("sub")
    if not isinstance(email, str) or not email.strip() or not isinstance(subject, str) or not subject:
        raise InvalidTokenError("Required identity claims are missing")
    return Identity(issuer=issuer, subject=subject, email=email.strip().lower())


def get_current_identity(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> Identity:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Bearer access token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return verify_access_token(credentials.credentials)
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Identity provider is not configured") from None
    except (InvalidTokenError, jwt.PyJWKClientError, ValueError):
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


def get_current_membership(
    identity: Identity = Depends(get_current_identity),
    tenant_header: str | None = Header(default=None, alias="X-Tenant-ID"),
    db: Session = Depends(get_db),
) -> TenantContext:
    """Resolve a requested tenant only after verifying a real membership row.

    X-Tenant-ID is a selector, never an authorization claim. RLS is set to this
    candidate tenant within the current transaction, then membership is checked.
    """
    try:
        tenant_id = UUID(tenant_header or "")
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="A valid X-Tenant-ID header is required") from None

    user = db.scalar(
        select(User).where(
            User.auth_issuer == identity.issuer,
            User.auth_subject == identity.subject,
            User.is_active.is_(True),
        )
    )
    if user is None:
        raise HTTPException(status_code=403, detail="User is not provisioned for Carbon ESG")

    # Set transaction-local RLS scope before reading the tenant-protected membership.
    db.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )
    membership = db.scalar(
        select(Membership).where(
            Membership.tenant_id == tenant_id,
            Membership.user_id == user.id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=403, detail="No membership in the requested organization")
    if membership.role not in {"owner", "admin", "manager", "reviewer", "viewer"}:
        raise HTTPException(status_code=403, detail="Membership role is not recognized")
    return TenantContext(tenant_id=tenant_id, user_id=user.id, role=membership.role)


def require_roles(*allowed_roles: str):
    allowed = frozenset(allowed_roles)
    if not allowed or not allowed.issubset({"owner", "admin", "manager", "reviewer", "viewer"}):
        raise ValueError("At least one valid Carbon ESG role is required")

    def dependency(context: TenantContext = Depends(get_current_membership)) -> TenantContext:
        if context.role not in allowed:
            raise HTTPException(status_code=403, detail="Insufficient organization permissions")
        return context

    return dependency
