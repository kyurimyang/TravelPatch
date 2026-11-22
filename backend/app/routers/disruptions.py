from typing import Annotated

from fastapi import APIRouter, Depends

from app.llm.provider import LLMProvider
from app.routers.deps import charged_provider
from app.schemas.disruption import InterpretRequest, InterpretResponse
from app.services.disruption_service import interpret_disruption

router = APIRouter(prefix="/disruptions", tags=["disruptions"])


# Plain `def`: the LLM call blocks, so FastAPI runs it in a worker thread.
@router.post("/interpret", response_model=InterpretResponse)
def interpret(
    req: InterpretRequest, provider: Annotated[LLMProvider, Depends(charged_provider)]
) -> InterpretResponse:
    return interpret_disruption(req, provider)
