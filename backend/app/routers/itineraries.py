from typing import Annotated

from fastapi import APIRouter, Depends

from app.llm.parser import parse_itinerary
from app.llm.provider import LLMOutputError, LLMProvider
from app.routers.deps import charged_provider
from app.schemas.itinerary import ParseProblem, ParseRequest, ParseResponse, PartialRead
from app.services.itinerary_draft import build_draft, read_count, reads_short

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
    if reads_short(parsed, req.text):
        # The model sometimes closes its answer early (a "※" remark after day 1 read as the
        # end): a well-formed but partial answer. Ask once more, keep the answer that read more.
        try:
            again = parse_itinerary(provider, req.text)
        except LLMOutputError:
            again = None
        if again is not None and read_count(again, req.text)[0] > read_count(parsed, req.text)[0]:
            parsed = again
    if not any(day.items for day in parsed.days):
        return ParseResponse(
            status="manual",
            draft=None,
            problem=ParseProblem(code="NOTHING_FOUND", detail="no item in the text"),
        )
    read, written = read_count(parsed, req.text)
    partial = PartialRead(read=read, written=written) if reads_short(parsed, req.text) else None
    return ParseResponse(status="ok", draft=build_draft(parsed, req.text), partial=partial)
