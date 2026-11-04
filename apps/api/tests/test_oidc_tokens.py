from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app import auth


@pytest.fixture
def signing_keys(monkeypatch):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setenv("OIDC_ISSUER", "https://identity.example.test/")
    monkeypatch.setenv("OIDC_AUDIENCE", "carbon-esg-api")
    monkeypatch.setenv("OIDC_JWKS_URL", "https://identity.example.test/.well-known/jwks.json")
    auth._jwks_client.cache_clear()
    monkeypatch.setattr(
        auth,
        "_jwks_client",
        lambda: SimpleNamespace(
            get_signing_key_from_jwt=lambda token: SimpleNamespace(key=private_key.public_key())
        ),
    )
    return private_key


def make_token(private_key, **overrides):
    now = datetime.now(timezone.utc)
    claims = {
        "iss": "https://identity.example.test/",
        "aud": "carbon-esg-api",
        "sub": "provider|immutable-subject-123",
        "email": "reviewer@example.test",
        "email_verified": True,
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    claims.update(overrides)
    return jwt.encode(claims, private_key, algorithm="RS256")


def test_valid_oidc_access_token_returns_stable_identity(signing_keys):
    identity = auth.verify_access_token(make_token(signing_keys))
    assert identity.issuer == "https://identity.example.test/"
    assert identity.subject == "provider|immutable-subject-123"
    assert identity.email == "reviewer@example.test"


def test_rejects_wrong_audience(signing_keys):
    with pytest.raises(auth.InvalidTokenError):
        auth.verify_access_token(make_token(signing_keys, aud="another-api"))


def test_rejects_unverified_email(signing_keys):
    with pytest.raises(auth.InvalidTokenError):
        auth.verify_access_token(make_token(signing_keys, email_verified=False))


def test_rejects_expired_token(signing_keys):
    expired = datetime.now(timezone.utc) - timedelta(minutes=5)
    with pytest.raises(auth.InvalidTokenError):
        auth.verify_access_token(
            make_token(signing_keys, exp=expired, iat=expired - timedelta(minutes=5))
        )
