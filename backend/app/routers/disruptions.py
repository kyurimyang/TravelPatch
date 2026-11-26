from typing import Annotated

from fastapi import APIRouter, Depends

from app.llm.provider import LLMProvider
from app.routers.deps import charged_provider
from app.schemas.disruption import BuildRequest, InterpretRequest, InterpretResponse
from app.services.disruption_service import build_disruption, interpret_disruption

router = APIRouter(prefix="/disruptions", tags=["disruptions"])


# Plain `def`: the LLM call blocks, so FastAPI runs it in a worker thread.
@router.post("/interpret", response_model=InterpretResponse)
def interpret(
    req: InterpretRequest, provider: Annotated[LLMProvider, Depends(charged_provider)]
) -> InterpretResponse:
    return interpret_disruption(req, provider)


@router.post("/build", response_model=InterpretResponse)
def build(req: BuildRequest) -> InterpretResponse:
    """The rules again on edited drafts (a fixed chip, an answered question). No LLM, so no
    key and no guest charge: the same rules the interpret call ran."""
    return build_disruption(req)
