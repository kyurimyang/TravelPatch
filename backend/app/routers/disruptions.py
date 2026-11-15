from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.llm.provider import LLMConfigError, LLMProvider, OpenAIProvider
from app.schemas.disruption import InterpretRequest, InterpretResponse
from app.services.disruption_service import interpret_disruption

router = APIRouter(prefix="/disruptions", tags=["disruptions"])


@lru_cache(maxsize=1)
def _openai() -> OpenAIProvider:
    return OpenAIProvider()


def get_provider() -> LLMProvider:
    # A dependency so tests can swap in a fake provider with app.dependency_overrides.
    try:
        return _openai()
    except LLMConfigError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


# Plain `def`: the LLM call blocks, so FastAPI runs it in a worker thread.
@router.post("/interpret", response_model=InterpretResponse)
def interpret(
    req: InterpretRequest, provider: Annotated[LLMProvider, Depends(get_provider)]
) -> InterpretResponse:
    return interpret_disruption(req, provider)
