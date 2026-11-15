from types import SimpleNamespace

import pytest
from pydantic import BaseModel, ValidationError

from app.llm.provider import LLMOutputError, OpenAIProvider


class Answer(BaseModel):
    n: int


def _completion(parsed=None, refusal=None):
    message = SimpleNamespace(parsed=parsed, refusal=refusal)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeClient:
    """Stands in for openai.OpenAI: replays queued results, counts calls."""

    def __init__(self, results):
        self._results = list(results)
        self.calls = 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(parse=self._parse))

    def _parse(self, **kwargs):
        self.calls += 1
        result = self._results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _provider(client):
    return OpenAIProvider(client=client, model="test-model")


def _call(provider):
    return provider.complete_json(system="s", user="u", schema=Answer)


def test_returns_parsed_answer_on_first_try():
    client = FakeClient([_completion(parsed=Answer(n=1))])
    assert _call(_provider(client)) == Answer(n=1)
    assert client.calls == 1


def test_retries_once_after_refusal_then_succeeds():
    client = FakeClient([_completion(refusal="no"), _completion(parsed=Answer(n=2))])
    assert _call(_provider(client)) == Answer(n=2)
    assert client.calls == 2


def test_retries_once_after_schema_mismatch():
    try:
        Answer.model_validate({"n": "x"})
    except ValidationError as exc:
        mismatch = exc
    client = FakeClient([mismatch, _completion(parsed=Answer(n=3))])
    assert _call(_provider(client)) == Answer(n=3)
    assert client.calls == 2


def test_raises_after_second_failure_and_does_not_retry_again():
    client = FakeClient([_completion(refusal="no"), _completion(refusal="no")])
    with pytest.raises(LLMOutputError):
        _call(_provider(client))
    assert client.calls == 2
