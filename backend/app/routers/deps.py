"""Dependencies shared by routers. Tests swap them with app.dependency_overrides."""

from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request

from app.llm.provider import LLMConfigError, LLMProvider, OpenAIProvider
from app.services.auth import AuthConfigError, AuthError, TokenVerifier, get_verifier
from app.services.guest_quota import GuestQuota, Kind
from app.services.places_client import GooglePlacesClient, PlacesConfigError


@lru_cache(maxsize=1)
def _openai() -> OpenAIProvider:
    return OpenAIProvider()


def get_provider() -> LLMProvider:
    # One function for every LLM route, so a single override replaces the model everywhere.
    try:
        return _openai()
    except LLMConfigError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@lru_cache(maxsize=1)
def _google_places() -> GooglePlacesClient:
    return GooglePlacesClient()


def get_places_client() -> GooglePlacesClient:
    try:
        return _google_places()
    except PlacesConfigError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


# Optional versions: features that work without the key (the solver itself) get None instead of
# a 503, so a closure is still solved offline, just without searched substitutes.
def get_provider_optional() -> LLMProvider | None:
    try:
        return _openai()
    except LLMConfigError:
        return None


def get_places_client_optional() -> GooglePlacesClient | None:
    try:
        return _google_places()
    except PlacesConfigError:
        return None


# --- Who is calling, and the guests' daily limits (decision 2026-11-22) ---


@dataclass(frozen=True)
class Caller:
    user_id: str | None  # None = guest
    ip: str


def get_verifier_optional() -> TokenVerifier | None:
    try:
        return get_verifier()
    except AuthConfigError:
        return None


@lru_cache(maxsize=1)
def get_guest_quota() -> GuestQuota:
    return GuestQuota()


def _client_ip(request: Request) -> str:
    # Behind Vercel's rewrite and Render's proxy the socket peer is a proxy. Vercel overwrites
    # X-Forwarded-For with the browser's IP and Render appends its own hop, so the left-most
    # entry is the user. A caller going to Render directly can forge it: the guests' total
    # limit is what bounds that case.
    forwarded = request.headers.get("x-forwarded-for", "")
    first = forwarded.split(",")[0].strip()
    if first:
        return first
    return request.client.host if request.client else "unknown"


def get_caller(
    request: Request,
    verifier: Annotated[TokenVerifier | None, Depends(get_verifier_optional)],
    authorization: Annotated[str | None, Header()] = None,
) -> Caller:
    """No Authorization header = guest. A header that cannot be trusted is a 401, not a guest:
    a broken token refresh on the front would otherwise look like a used-up limit."""
    ip = _client_ip(request)
    if not authorization:
        return Caller(user_id=None, ip=ip)
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Authorization must be 'Bearer <token>'")
    if verifier is None:
        raise HTTPException(status_code=503, detail="SUPABASE_URL is not set: cannot check login")
    try:
        return Caller(user_id=verifier.user_id(token), ip=ip)
    except AuthError as e:
        raise HTTPException(status_code=401, detail=f"invalid token ({e})") from e


def allow(caller: Caller, kind: Kind, quota: GuestQuota) -> bool:
    """Signed-in users are not counted; a guest uses one call of the day's limit."""
    return caller.user_id is not None or quota.charge(kind, caller.ip)


def _refuse(kind: Kind) -> HTTPException:
    return HTTPException(status_code=429, detail=f"guest daily limit reached ({kind})")


def charged_provider(
    caller: Annotated[Caller, Depends(get_caller)],
    quota: Annotated[GuestQuota, Depends(get_guest_quota)],
    provider: Annotated[LLMProvider, Depends(get_provider)],
) -> LLMProvider:
    """get_provider, after counting a guest's call. Routes that always call the LLM use this."""
    if not allow(caller, Kind.LLM, quota):
        raise _refuse(Kind.LLM)
    return provider


def charged_places(
    caller: Annotated[Caller, Depends(get_caller)],
    quota: Annotated[GuestQuota, Depends(get_guest_quota)],
    places: Annotated[GooglePlacesClient, Depends(get_places_client)],
) -> GooglePlacesClient:
    """get_places_client, after counting a guest's call."""
    if not allow(caller, Kind.PLACES, quota):
        raise _refuse(Kind.PLACES)
    return places
