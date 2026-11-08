"""Verify Neon Managed Better Auth JWTs for the separate FastAPI service."""
import os
from functools import lru_cache
from urllib.parse import urlparse

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from jwt.exceptions import PyJWTError

bearer_scheme = HTTPBearer(auto_error=False)


def _auth_settings() -> tuple[str, str, str]:
    base_url = os.getenv("NEON_AUTH_BASE_URL", "").strip().rstrip("/")
    jwks_url = os.getenv("NEON_AUTH_JWKS_URL", "").strip()
    if not base_url:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Authentication is not configured")
    parsed = urlparse(base_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Invalid authentication configuration")
    origin = f"{parsed.scheme}://{parsed.netloc}"
    return base_url, jwks_url or f"{base_url}/.well-known/jwks.json", origin


@lru_cache(maxsize=4)
def _jwks_client(jwks_url: str) -> PyJWKClient:
    return PyJWKClient(jwks_url, cache_jwk_set=True, lifespan=300, timeout=5)


def verify_neon_token(token: str) -> dict:
    _base_url, jwks_url, issuer = _auth_settings()
    try:
        signing_key = _jwks_client(jwks_url).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["EdDSA"],
            issuer=issuer,
            audience=issuer,
            options={"require": ["exp", "iss", "aud", "sub"]},
        )
        if not isinstance(claims.get("sub"), str) or not claims["sub"]:
            raise ValueError("Missing subject")
        return claims
    except (PyJWTError, ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return verify_neon_token(credentials.credentials)
