from fastapi.testclient import TestClient

from app.main import app


def test_health_answers_without_any_service() -> None:
    # conftest makes any LLM / Places use fail the test, so this also proves none is touched.
    res = TestClient(app).get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
