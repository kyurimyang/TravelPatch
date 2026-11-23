from app.llm.provider import LLM_TIMEOUT_SECONDS, OpenAIProvider


def test_openai_calls_have_a_time_limit_and_no_hidden_retries():
    # The SDK default is 10 minutes and 2 retries of its own: one slow answer could hold the
    # single server's worker for half an hour.
    client = OpenAIProvider(api_key="sk-test")._client
    assert client.timeout == LLM_TIMEOUT_SECONDS
    assert client.max_retries == 0
