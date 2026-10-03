from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_live_probe_is_ok():
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_runtime_config_same_origin_by_default():
    response = client.get("/api/runtime-config")
    assert response.status_code == 200
    assert response.json()["interview_api_origin"] == ""
