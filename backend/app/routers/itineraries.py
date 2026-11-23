from concurrent.futures import ThreadPoolExecutor
from typing import Annotated

from fastapi import APIRouter, Depends

from app.llm.parser import ParsedItinerary, parse_itinerary
from app.llm.provider import LLMOutputError, LLMProvider
from app.routers.deps import charged_provider
from app.schemas.itinerary import ParseProblem, ParseRequest, ParseResponse, PartialRead
from app.services.itinerary_draft import build_draft, read_count, reads_short
from app.services.itinerary_split import split_days

router = APIRouter(prefix="/itineraries", tags=["itineraries"])

# Days parsed at once. A long trip waits for the slowest day, not for the sum of them.
MAX_PARALLEL_DAYS = 4


def _parse_text(provider: LLMProvider, text: str) -> ParsedItinerary | None:
    """One text (a day, or the whole paste) -> its parse, or None when the model failed.

    The model sometimes closes its answer early (a "※" remark read as the end): a well-formed
    but partial answer. It is asked once more, and the answer that read more is kept."""
    try:
        parsed = parse_itinerary(provider, text)
    except LLMOutputError:
        return None
    if reads_short(parsed, text):
        try:
            again = parse_itinerary(provider, text)
        except LLMOutputError:
            again = None
        if again is not None and read_count(again, text)[0] > read_count(parsed, text)[0]:
            parsed = again
    return parsed


# Plain `def`: the LLM calls block, so FastAPI runs this in a worker thread.
@router.post("/parse", response_model=ParseResponse)
def parse(
    req: ParseRequest, provider: Annotated[LLMProvider, Depends(charged_provider)]
) -> ParseResponse:
    """Step ①: pasted text -> draft the Confirm screen shows. Nothing is stored.

    A text with day headings is parsed one day per call, in parallel (services/itinerary_split).
    An LLM failure is not an HTTP error: the screen gets status "manual" and offers to type the
    plan in by hand (invariant 4: retry once inside the provider, then hand over to the user).
    A day that could not be read leaves the rest standing, and `partial` says what is missing.
    """
    chunks = split_days(req.text)
    if len(chunks) == 1:
        parts = [_parse_text(provider, req.text)]
    else:
        with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL_DAYS, len(chunks))) as pool:
            parts = list(pool.map(lambda chunk: _parse_text(provider, chunk), chunks))
    if all(p is None for p in parts):
        return ParseResponse(
            status="manual",
            draft=None,
            problem=ParseProblem(code="LLM_FAILED", detail="the model gave no usable answer"),
        )
    parsed = ParsedItinerary(days=[day for p in parts if p is not None for day in p.days])
    if not any(day.items for day in parsed.days):
        return ParseResponse(
            status="manual",
            draft=None,
            problem=ParseProblem(code="NOTHING_FOUND", detail="no item in the text"),
        )
    read, written = read_count(parsed, req.text)
    partial = PartialRead(read=read, written=written) if reads_short(parsed, req.text) else None
    return ParseResponse(status="ok", draft=build_draft(parsed, req.text), partial=partial)
