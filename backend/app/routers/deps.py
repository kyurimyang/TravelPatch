"""Dependencies shared by routers. Tests swap them with app.dependency_overrides."""

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request

from app.llm.provider import LLMConfigError, LLMProvider, OpenAIProvider, interpret_provider
from app.services.auth import AuthConfigError, AuthError, TokenVerifier, get_verifier
from app.services.guest_quota import GuestQuota, Kind, store_from_env
from app.services.places_client import GooglePlacesClient, PlacesConfigError
from app.services.routes_client import GoogleRoutesClient, RoutesConfigError, routes_enabled

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _openai() -> OpenAIProvider:
    return OpenAIProvider()


@lru_cache(maxsize=1)
def _openai_interpret() -> OpenAIProvider:
    return interpret_provider()


def get_interpret_provider() -> LLMProvider:
    """The model that reads the one-line input (llm/provider.INTERPRET_MODEL)."""
    try:
        return _openai_interpret()
    except LLMConfigError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


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


@lru_cache(maxsize=1)
def _google_routes() -> GoogleRoutesClient:
    return GoogleRoutesClient()


def get_routes_client_optional() -> GoogleRoutesClient | None:
    """None while the switch is off or without GOOGLE_ROUTES_API_KEY: the plan is built with
    estimated travel times (the default)."""
    if not routes_enabled():
        return None
    try:
        return _google_routes()
    except RoutesConfigError:
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
    try:
        store = store_from_env()
    except Exception:  # QUOTA_STORE=supabase but no keys: still limited, in memory
        log.warning("QUOTA_STORE is set but the database is not configured", exc_info=True)
        store = None
    return GuestQuota(store=store)


def _client_ip(request: Request) -> str:
    """The guest's IP, from headers a caller cannot set (measured 2026-11-22, decisions.md).

    Browser -> Vercel (rewrite) -> Cloudflare -> Render. Measured through Vercel, a forged
    X-Forwarded-For and x-vercel-forwarded-for were sometimes passed on as sent; only
    x-vercel-proxied-for always held the real IP (not in Vercel's docs: check it again if
    Vercel changes). On a direct call to Render, cf-connecting-ip is the real peer, written by
    Cloudflare. Gap: a direct caller can send its own x-vercel-proxied-for; the guests' total
    limit bounds that. request.client is last and only for local runs: on Render, uvicorn
    rewrites it from X-Forwarded-For.
    """
    for name in ("x-vercel-proxied-for", "cf-connecting-ip"):
        value = request.headers.get(name, "").split(",")[0].strip()
        if value:
            return value
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
    """One call of the day's limit: the signed-in user's own, or the guest's (per IP and in total).
    Signed-in users are counted too (2026-11-23): sign-up has no e-mail check."""
    if caller.user_id is not None:
        return quota.charge_user(kind, caller.user_id)
    return quota.charge(kind, caller.ip)


def _refuse(kind: Kind) -> HTTPException:
    return HTTPException(status_code=429, detail=f"daily limit reached ({kind})")


def charged_provider(
    caller: Annotated[Caller, Depends(get_caller)],
    quota: Annotated[GuestQuota, Depends(get_guest_quota)],
    provider: Annotated[LLMProvider, Depends(get_provider)],
) -> LLMProvider:
    """get_provider, after counting a guest's call. Routes that always call the LLM use this."""
    if not allow(caller, Kind.LLM, quota):
        raise _refuse(Kind.LLM)
    return provider


def charged_interpreter(
    caller: Annotated[Caller, Depends(get_caller)],
    quota: Annotated[GuestQuota, Depends(get_guest_quota)],
    provider: Annotated[LLMProvider, Depends(get_interpret_provider)],
) -> LLMProvider:
    """charged_provider for POST /disruptions/interpret (its own model, same guest limit)."""
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
