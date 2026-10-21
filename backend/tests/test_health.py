"""Validate the public API contract without external services."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def test_health_contract(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "devpilot-api",
        "version": "0.2.0",
    }


def test_openapi_exposes_health_response(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    endpoint = schema["paths"]["/api/v1/health"]["get"]
    assert endpoint["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/HealthResponse"
    }


def test_unknown_route_returns_404(client):
    assert client.get("/api/v1/not-found").status_code == 404


def test_interactive_docs_available(client):
    assert client.get("/docs").status_code == 200
