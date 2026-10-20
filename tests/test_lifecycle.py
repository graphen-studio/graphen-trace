"""Tests for passive collector startup, recovery, and shutdown."""

import asyncio
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from graphen_trace.api import lifecycle
from graphen_trace.api.app import create_app
from graphen_trace.services.discovery import AgentInstallation


def test_service_starts_idle_and_collects_only_after_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A detected installation starts collecting only after API selection."""
    monkeypatch.setattr(
        lifecycle,
        "settings",
        replace(
            lifecycle.settings,
            database_path=tmp_path / "trace.db",
            opencode_database=tmp_path / "missing.db",
            opencode_url=None,
            opencode_service_file=tmp_path / "missing-service.json",
        ),
    )
    monkeypatch.setattr(
        lifecycle,
        "discover_agents",
        lambda: [AgentInstallation("opencode", "/example/opencode", "9.0.0", True)],
    )
    with TestClient(create_app()) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/collection").json()["state"] == "not_started"
        assert (
            client.post("/api/collection", json={"agent": "opencode"}).status_code
            == 200
        )
        client.portal.call(asyncio.sleep, 0.05)
        assert client.get("/api/collection").json()["state"] == "unavailable"
        assert client.get("/api/sessions").json() == {"items": []}
