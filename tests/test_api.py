"""Tests for initial dashboard API routes."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from graphen_trace.api.app import create_app

FRONTEND_INDEX = (
    Path(__file__).parents[1] / "graphen_trace" / "web" / "dist" / "index.html"
)


@pytest.fixture
def client() -> TestClient:
    """Creates a client for the Graphen Trace API."""
    return TestClient(create_app())


def test_health_route_is_served(client: TestClient) -> None:
    """Health route returns service status."""
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/api/not-implemented").status_code == 404


@pytest.mark.skipif(not FRONTEND_INDEX.is_file(), reason="Build frontend assets first")
def test_frontend_is_served(client: TestClient) -> None:
    """The SPA fallback returns the compiled frontend when present."""
    assert client.get("/").status_code == 200


def test_proxy_route_is_only_enabled_explicitly() -> None:
    """The proxy feature remains disabled unless explicitly requested."""
    passive_app = create_app()
    proxy_app = create_app(proxy_enabled=True)

    assert not passive_app.state.proxy_enabled
    assert proxy_app.state.proxy_enabled
