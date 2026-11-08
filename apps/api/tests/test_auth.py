from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import auth
from app.main import app


class FakeSigningKey:
    def __init__(self, key):
        self.key = key


class FakeJwksClient:
    def __init__(self, key):
        self.key = key

    def get_signing_key_from_jwt(self, _token):
        return FakeSigningKey(self.key)


def test_protected_identity_endpoint_rejects_missing_bearer():
    response = TestClient(app).get("/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Bearer token required"


def test_neon_ed25519_token_is_verified(monkeypatch):
    base_url = "https://auth.example.neon.tech/neondb/auth"
    origin = "https://auth.example.neon.tech"
    private_key = Ed25519PrivateKey.generate()
    monkeypatch.setenv("NEON_AUTH_BASE_URL", base_url)
    monkeypatch.setenv("NEON_AUTH_JWKS_URL", f"{base_url}/.well-known/jwks.json")
    monkeypatch.setattr(auth, "_jwks_client", lambda _url: FakeJwksClient(private_key.public_key()))

    token = jwt.encode(
        {
            "sub": "user-123",
            "iss": origin,
            "aud": origin,
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
            "email": "test@example.com",
        },
        private_key,
        algorithm="EdDSA",
        headers={"kid": "test-key"},
    )

    claims = auth.verify_neon_token(token)
    assert claims["sub"] == "user-123"
    assert claims["email"] == "test@example.com"


def test_neon_token_rejects_wrong_issuer(monkeypatch):
    base_url = "https://auth.example.neon.tech/neondb/auth"
    private_key = Ed25519PrivateKey.generate()
    monkeypatch.setenv("NEON_AUTH_BASE_URL", base_url)
    monkeypatch.setenv("NEON_AUTH_JWKS_URL", f"{base_url}/.well-known/jwks.json")
    monkeypatch.setattr(auth, "_jwks_client", lambda _url: FakeJwksClient(private_key.public_key()))

    token = jwt.encode(
        {
            "sub": "user-123",
            "iss": "https://attacker.example",
            "aud": "https://auth.example.neon.tech",
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
        },
        private_key,
        algorithm="EdDSA",
        headers={"kid": "test-key"},
    )

    with pytest.raises(HTTPException) as exc:
        auth.verify_neon_token(token)
    assert exc.value.status_code == 401
