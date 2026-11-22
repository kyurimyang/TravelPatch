"""TokenVerifier with a key made in the test: no network, no real Supabase project."""

import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from app.services.auth import AuthError, TokenVerifier

URL = "https://example.supabase.co"
PROJECT_KEY = ec.generate_private_key(ec.SECP256R1())
OTHER_KEY = ec.generate_private_key(ec.SECP256R1())


class FakeJwks:
    """Stands in for PyJWKClient: always hands back the project's public key."""

    def get_signing_key_from_jwt(self, token: str) -> SimpleNamespace:
        return SimpleNamespace(key=PROJECT_KEY.public_key())


def _token(key: ec.EllipticCurvePrivateKey = PROJECT_KEY, **overrides: object) -> str:
    claims = {
        "sub": "user-1",
        "aud": "authenticated",
        "iss": f"{URL}/auth/v1",
        "exp": int(time.time()) + 3600,
    }
    claims.update(overrides)
    return jwt.encode(claims, key, algorithm="ES256")


@pytest.fixture
def verifier() -> TokenVerifier:
    return TokenVerifier(URL + "/", jwks=FakeJwks())  # trailing slash is tolerated


def test_valid_token_gives_the_user_id(verifier: TokenVerifier) -> None:
    assert verifier.user_id(_token()) == "user-1"


@pytest.mark.parametrize(
    "token",
    [
        pytest.param(_token(exp=int(time.time()) - 10), id="expired"),
        pytest.param(_token(aud="anon"), id="anon-key-not-a-user"),
        pytest.param(_token(iss="https://other.supabase.co/auth/v1"), id="other-project"),
        pytest.param(_token(OTHER_KEY), id="forged-signature"),
        pytest.param("not-a-jwt", id="garbage"),
    ],
)
def test_untrusted_tokens_are_refused(verifier: TokenVerifier, token: str) -> None:
    with pytest.raises(AuthError):
        verifier.user_id(token)
