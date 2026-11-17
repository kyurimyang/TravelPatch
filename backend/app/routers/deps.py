"""Dependencies shared by routers. Tests swap them with app.dependency_overrides."""

from functools import lru_cache

from fastapi import HTTPException

from app.llm.provider import LLMConfigError, LLMProvider, OpenAIProvider
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
