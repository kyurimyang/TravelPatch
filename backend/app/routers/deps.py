"""Dependencies shared by routers. Tests swap them with app.dependency_overrides."""

from functools import lru_cache

from fastapi import HTTPException

from app.llm.provider import LLMConfigError, LLMProvider, OpenAIProvider


@lru_cache(maxsize=1)
def _openai() -> OpenAIProvider:
    return OpenAIProvider()


def get_provider() -> LLMProvider:
    # One function for every LLM route, so a single override replaces the model everywhere.
    try:
        return _openai()
    except LLMConfigError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
