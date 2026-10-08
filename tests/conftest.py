import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture(autouse=True)
def no_live_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Tests must not make real network or paid API requests")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", blocked)


@pytest.fixture
def client(tmp_path):
    settings = Settings(database_path=str(tmp_path / "test.db"))
    with TestClient(create_app(settings), headers={"X-Requested-With": "quiz-app"}) as value:
        yield value


@pytest.fixture
def seeded(client):
    response = client.post("/api/demo/seed")
    assert response.status_code == 200
    return response.json()
