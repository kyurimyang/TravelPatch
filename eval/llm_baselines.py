"""Comparison methods (c) LLM-only and (d) LLM + validator, with an on-disk answer cache.

(c) asks the LLM for a plan once and reports it as is; violations are counted, not hidden.
(d) runs the independent validator on the answer and, when it finds problems, asks again with
the problems listed (up to `REPAIRS` times). If the plan is still invalid it is rejected, like
the product would do (invariant 3): the row then has no plan, with the reason "validator_rejected".

The cache makes a rerun free and reproducible: the same prompt returns the recorded answer and
the recorded latency, so the experiment does not depend on the model answering the same twice.
"""

import hashlib
import json
import time
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from app.engine.cost import compute_cost
from app.engine.presets import DEFAULT_WEIGHTS
from app.engine.validator import Violation, validate
from app.llm.provider import LLMError, LLMProvider
from app.schemas.recovery import RecoveryChange, RecoveryInput, RecoveryResult
from eval.llm_plan import (
    SYSTEM_PROMPT,
    LLMPlan,
    PlanFormatError,
    build_prompt,
    plan_to_changes,
    repair_prompt,
)

T = TypeVar("T", bound=BaseModel)
REPAIRS = 2  # extra asks in (d) after the first answer


class NoPlan(Exception):
    """The method produced no usable plan. `reason` goes in the results table."""

    def __init__(self, reason: str, ms: int = 0) -> None:
        super().__init__(reason)
        self.reason = reason
        self.ms = ms


class CachedProvider:
    """Wraps a provider: answers are stored in `cache_dir` keyed by the exact prompt."""

    def __init__(self, inner: LLMProvider, cache_dir: Path, model: str, run: int = 1) -> None:
        """`run` > 1 asks the model again for a repeated measurement: its answers are kept under
        their own keys. Run 1 keeps the keys used before repeats existed."""
        self._inner = inner
        self._dir = cache_dir
        self._model = model
        self._run = run
        self._dir.mkdir(parents=True, exist_ok=True)
        self.ms = 0.0  # latency of the calls since the last `take_ms`

    def take_ms(self) -> int:
        taken, self.ms = round(self.ms), 0.0
        return taken

    def complete_json(self, *, system: str, user: str, schema: type[T]) -> T:
        key = [self._model, schema.__name__, system, user]
        if self._run > 1:
            key.append(f"run{self._run}")
        digest = hashlib.sha256(json.dumps(key).encode()).hexdigest()
        path = self._dir / f"{digest}.json"
        if path.exists():
            record = json.loads(path.read_text(encoding="utf-8"))
        else:
            t0 = time.perf_counter()
            answer = self._inner.complete_json(system=system, user=user, schema=schema)
            ms = (time.perf_counter() - t0) * 1000
            record = {"answer": answer.model_dump(), "ms": ms, "model": self._model}
            path.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
        self.ms += record["ms"]
        return schema.model_validate(record["answer"])


def _ask(provider: CachedProvider, user: str) -> LLMPlan:
    try:
        return provider.complete_json(system=SYSTEM_PROMPT, user=user, schema=LLMPlan)
    except LLMError as exc:
        raise NoPlan("llm_error", provider.take_ms()) from exc


def _result(
    inp: RecoveryInput,
    name: str,
    changes: tuple[RecoveryChange, ...],
    problems: list[Violation],
    ms: int,
) -> RecoveryResult:
    cost = compute_cost(inp, changes, DEFAULT_WEIGHTS)
    return RecoveryResult(
        strategy=name,
        changes=changes,
        rc_total=cost.rc_total,
        rc_breakdown=cost.breakdown,
        preservation_rate=cost.preservation_rate,
        violations=len(problems),
        solver_ms=ms,
    )


def make_llm_only(provider: CachedProvider):
    def llm_only(inp: RecoveryInput) -> RecoveryResult:
        plan = _ask(provider, build_prompt(inp))
        ms = provider.take_ms()
        try:
            changes = plan_to_changes(inp, plan)
        except PlanFormatError as exc:
            raise NoPlan("unparseable", ms) from exc
        return _result(inp, "llm_only", changes, validate(inp, changes), ms)

    return llm_only


def make_llm_validated(provider: CachedProvider):
    def llm_validated(inp: RecoveryInput) -> RecoveryResult:
        user = build_prompt(inp)
        for _ in range(1 + REPAIRS):
            plan = _ask(provider, user)
            try:
                changes = plan_to_changes(inp, plan)
                problems = validate(inp, changes)
            except PlanFormatError as exc:
                changes, problems = (), [Violation(kind="format", activity_id="-", detail=str(exc))]
            if not problems:
                return _result(inp, "llm_validated", changes, [], provider.take_ms())
            user = repair_prompt(inp, plan, problems)
        raise NoPlan("validator_rejected", provider.take_ms())

    return llm_validated
