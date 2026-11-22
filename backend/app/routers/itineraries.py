from typing import Annotated

from fastapi import APIRouter, Depends

from app.llm.parser import parse_itinerary
from app.llm.provider import LLMOutputError, LLMProvider
from app.routers.deps import charged_provider
from app.schemas.itinerary import ParseProblem, ParseRequest, ParseResponse
from app.services.itinerary_draft import build_draft

router = APIRouter(prefix="/itineraries", tags=["itineraries"])


# Plain `def`: the LLM call blocks, so FastAPI runs it in a worker thread.
@router.post("/parse", response_model=ParseResponse)
def parse(
    req: ParseRequest, provider: Annotated[LLMProvider, Depends(charged_provider)]
) -> ParseResponse:
    """Step ①: pasted text -> draft the Confirm screen shows. Nothing is stored.

    An LLM failure is not an HTTP error: the screen gets status "manual" and offers to type the
    plan in by hand (invariant 4: retry once inside the provider, then hand over to the user).
    """
    try:
        parsed = parse_itinerary(provider, req.text)
    except LLMOutputError as e:
        return ParseResponse(
            status="manual", draft=None, problem=ParseProblem(code="LLM_FAILED", detail=str(e))
        )
    if not any(day.items for day in parsed.days):
        return ParseResponse(
            status="manual",
            draft=None,
            problem=ParseProblem(code="NOTHING_FOUND", detail="no item in the text"),
        )
    return ParseResponse(status="ok", draft=build_draft(parsed))
