from fastapi.testclient import TestClient

from app.main import app


def test_health_reports_ok_and_mock_providers() -> None:
    res = TestClient(app).get("/api/health")

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["llm_provider"] == "mock"
    assert body["image_provider"] == "mock"
