"""LLM provider abstraction. Never imported by the engine (invariant 1).

Every LLM call in the app goes through `LLMProvider.complete_json`, which forces the answer
into a Pydantic schema (invariant 4). On a parse failure or a schema mismatch it retries once,
then raises `LLMOutputError` so the caller can fall back to asking the user.
"""

import os
from pathlib import Path
from typing import Protocol, TypeVar

import openai
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

# .env sits at the repo root, three levels above backend/app/llm.
_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
DEFAULT_MODEL = "gpt-4o-mini"
MAX_ATTEMPTS = 2  # first try + one retry (invariant 4)


class LLMError(RuntimeError):
    """Base class: the LLM could not give a usable answer."""


class LLMConfigError(LLMError):
    """API key missing."""


class LLMOutputError(LLMError):
    """Answer was refused, not JSON, or did not match the schema, even after the retry."""


class LLMProvider(Protocol):
    def complete_json(self, *, system: str, user: str, schema: type[T]) -> T: ...


class OpenAIProvider:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        client: openai.OpenAI | None = None,
    ) -> None:
        if client is None:
            load_dotenv(_ENV_PATH)
            key = (api_key or os.environ.get("OPENAI_KEY", "")).strip()
            if not key:
                raise LLMConfigError("OPENAI_KEY is not set (see .env)")
            client = openai.OpenAI(api_key=key)
        self._client = client
        self._model = model or os.environ.get("OPENAI_MODEL") or DEFAULT_MODEL

    def complete_json(self, *, system: str, user: str, schema: type[T]) -> T:
        last_problem = "no attempt made"
        for _ in range(MAX_ATTEMPTS):
            try:
                completion = self._client.chat.completions.parse(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    response_format=schema,
                )
            except ValidationError as exc:
                last_problem = f"schema mismatch: {exc.error_count()} error(s)"
                continue
            except openai.LengthFinishReasonError:
                # Ran to max tokens (a repeating answer): unparseable, so retried like a schema
                # mismatch instead of crashing the request (invariant 4).
                last_problem = "answer cut off at the length limit"
                continue
            message = completion.choices[0].message
            if message.parsed is None:
                last_problem = f"refused or empty: {message.refusal or 'no content'}"
                continue
            return message.parsed
        raise LLMOutputError(last_problem)
