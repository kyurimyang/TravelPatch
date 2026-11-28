"""The patch with searched stand-in places (steps ⑦–⑧), shared by POST /recoveries and the live
tests so they test exactly what the user gets.

⑦ A closure, rain or "실내 우선": search substitutes first, then solve.
⑧ A plan that drops a piece: look for a similar place nearby and solve again, so "instead of
   dropping it, go here" can be offered (2026-11-24). Only kept when it changes something.

`may_search` is asked right before each search (the router charges a guest there), so a search
that is not needed costs nothing. I/O stays out of the engine.
"""

import logging
from collections.abc import Callable

from app.llm.provider import LLMProvider
from app.schemas.recovery import RecoveryInput, RecoveryResponse
from app.services.places_client import GooglePlacesClient
from app.services.recovery_service import run_recovery
from app.services.substitute_finder import add_substitutes, add_substitutes_for, wants_substitutes

# How many dropped pieces get a substitute search after the first solve (one LLM call and one
# Google search each), the most valuable first. Small on purpose: it runs on every patch
# that drops something.
MAX_DROP_SEARCHES = 2

log = logging.getLogger(__name__)


def dropped_worth_a_search(inp: RecoveryInput, response: RecoveryResponse) -> list[str]:
    """Activities some candidate drops and that have no substitute yet, highest tier first."""
    weight = {p.activity_id: p.tier.weight for p in inp.preferences}
    has_sub = {s.replaces for s in inp.substitutes}
    dropped = {
        c.activity_id
        for r in response.candidates
        for c in r.changes
        if c.op == "drop" and c.activity_id not in has_sub and c.activity_id in weight
    }
    return sorted(dropped, key=lambda a: (-weight[a], a))[:MAX_DROP_SEARCHES]


def log_unused_substitutes(inp: RecoveryInput, response: RecoveryResponse) -> None:
    """Pieces that had stand-ins found but that every candidate still drops: the stand-ins did not
    fit (time, hours, the next booking). Logged so "found but none fit" is told apart from "none
    found" (user test 2026-11-28: a closed dinner came back as a plain drop)."""
    has_sub: dict[str, int] = {}
    for s in inp.substitutes:
        has_sub[s.replaces] = has_sub.get(s.replaces, 0) + 1
    for aid, n in sorted(has_sub.items()):
        ops = {c.op for r in response.candidates for c in r.changes if c.activity_id == aid}
        if ops == {"drop"}:
            log.warning("%s: %d substitutes found, every candidate still drops it", aid, n)


def recover_with_search(
    inp: RecoveryInput,
    provider: LLMProvider | None,
    places: GooglePlacesClient | None,
    may_search: Callable[[], bool] = lambda: True,
) -> tuple[RecoveryInput, RecoveryResponse]:
    """The input the answer was solved on (with any substitutes found) and the answer.
    Without a provider or Google, the engine alone (the same answer as a server with no keys)."""
    can = provider is not None and places is not None
    if can and wants_substitutes(inp) and may_search():
        inp = add_substitutes(inp, provider, places)
    response = run_recovery(inp)
    targets = dropped_worth_a_search(inp, response)
    if targets and can and may_search():
        richer = add_substitutes_for(inp, targets, provider, places)
        if richer is not inp:
            inp, response = richer, run_recovery(richer)
    log_unused_substitutes(inp, response)
    return inp, response
