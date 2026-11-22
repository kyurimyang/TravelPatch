"""Who is calling: a signed-in Supabase user or a guest (decision 2026-11-22).

Supabase signs its access tokens with an asymmetric key (ES256) and publishes the public keys
at /auth/v1/.well-known/jwks.json, so the backend checks a token on its own: no call to
Supabase per request, only a key download now and then (PyJWKClient caches it).
"""

import os
from functools import lru_cache
from pathlib import Path

import jwt
from dotenv import load_dotenv

# .env sits at the repo root, three levels above backend/app/services.
_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
ALGORITHMS = ["ES256"]
AUDIENCE = "authenticated"  # Supabase's audience for a signed-in user (anon tokens say "anon")
JWKS_CACHE_SECONDS = 600


class AuthError(RuntimeError):
    """A token was sent but cannot be trusted (expired, forged, another project's)."""


class AuthConfigError(AuthError):
    """SUPABASE_URL missing: no token can be checked."""


class TokenVerifier:
    def __init__(self, supabase_url: str, jwks: jwt.PyJWKClient | None = None) -> None:
        base = supabase_url.rstrip("/")
        self.issuer = f"{base}/auth/v1"
        self._jwks = jwks or jwt.PyJWKClient(
            f"{self.issuer}/.well-known/jwks.json", cache_keys=True, lifespan=JWKS_CACHE_SECONDS
        )

    def user_id(self, token: str) -> str:
        """The user's id (`sub`) when the token is valid, else AuthError."""
        try:
            key = self._jwks.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                key.key,
                algorithms=ALGORITHMS,
                audience=AUDIENCE,
                issuer=self.issuer,
                options={"require": ["exp", "sub"]},
            )
        except jwt.PyJWTError as e:  # bad signature, expired, wrong audience, unknown kid...
            raise AuthError(type(e).__name__) from e
        return str(claims["sub"])


@lru_cache(maxsize=1)
def get_verifier() -> TokenVerifier:
    load_dotenv(_ENV_PATH)
    url = os.environ.get("SUPABASE_URL", "").strip()
    if not url:
        raise AuthConfigError("SUPABASE_URL is not set (see .env)")
    return TokenVerifier(url)
