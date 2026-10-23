"""Tests for adapter factories registered by agent name."""

from dataclasses import replace
from pathlib import Path

from graphen_trace.adapters.opencode.discovery import OpenCodeAdapter
from graphen_trace.adapters.pi.collector import PiCollector
from graphen_trace.adapters.pi.discovery import PiAdapter
from graphen_trace.adapters.registry import ADAPTERS
from graphen_trace.config.settings import settings
from graphen_trace.services.discovery import AgentInstallation
from graphen_trace.services.storage import Storage


def test_registry_creates_source_specific_runtimes(tmp_path: Path) -> None:
    """Each registered adapter owns its polling and optional live collectors."""
    storage = Storage(tmp_path / "graphen.db")
    storage.initialize()
    runtime_settings = replace(
        settings,
        opencode_database=tmp_path / "opencode.db",
        pi_sessions_dir=tmp_path / "pi-sessions",
    )
    installations = {
        "opencode": AgentInstallation("opencode", "/bin/opencode", "2.0.32", True),
        "pi": AgentInstallation("pi", "/bin/pi", "1.4.0", True),
    }

    assert set(ADAPTERS) == set(installations)
    for name, adapter_type in ADAPTERS.items():
        adapter = adapter_type()
        installation = installations[name]
        assert adapter.supports(installation)
        runtime = adapter.create_runtime(installation, runtime_settings, storage)
        assert runtime.collector.agent_name == name

        if name == "opencode":
            assert runtime.live_collector is not None
        else:
            assert isinstance(runtime.collector, PiCollector)
            assert runtime.live_collector is None


def test_adapter_rejects_an_installation_for_another_agent() -> None:
    """Registry factories validate the installation before runtime creation."""
    installation = AgentInstallation("pi", "/bin/pi", "1.4.0", True)

    assert not OpenCodeAdapter().supports(installation)
    assert not PiAdapter().supports(
        AgentInstallation("opencode", "/bin/opencode", "2.0.32", True)
    )
