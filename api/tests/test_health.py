from fastapi.testclient import TestClient


def test_health_reports_ok_and_mock_providers(client: TestClient) -> None:
    res = client.get("/api/health")

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["llm_provider"] == "mock"
    assert body["image_provider"] == "mock"
