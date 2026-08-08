"""Health endpoint behaviour, including the degraded path.

The failure case matters as much as the happy one: a broken database must never
be reported as a healthy service.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from api.main import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app(), raise_server_exceptions=False) as test_client:
        yield test_client


def test_health_reports_ok_when_database_is_reachable(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("api.routers.health.check_connection", lambda: None)

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["version"] == "0.1.0"


def test_health_reports_degraded_when_database_is_unreachable(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode() -> None:
        raise ConnectionRefusedError("no route to database")

    monkeypatch.setattr("api.routers.health.check_connection", explode)

    response = client.get("/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["database"] == "error"
    assert body["detail"] == "ConnectionRefusedError"


def test_openapi_schema_is_generated(client: TestClient) -> None:
    """The web client is generated from this schema, so it must stay valid."""
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/health" in response.json()["paths"]
