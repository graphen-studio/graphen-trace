"""Tests for local server logging and graceful CLI shutdown."""

from dataclasses import replace

import pytest

from graphen_trace.commands import serve as serve_module
from graphen_trace.commands.serve import ServeCommand
from graphen_trace.services import server


@pytest.mark.parametrize("enabled", [False, True])
def test_server_access_logging_follows_settings(
    monkeypatch: pytest.MonkeyPatch,
    enabled: bool,
) -> None:
    """Configures Uvicorn access logs from the Graphen setting."""
    monkeypatch.setattr(
        server,
        "settings",
        replace(server.settings, access_log=enabled),
    )

    assert server.create_server().config.access_log is enabled


def test_serve_command_treats_keyboard_interrupt_as_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reports Ctrl+C as a normal shutdown instead of a CLI failure."""
    output = []

    def interrupt_server(*, proxy_enabled: bool) -> None:
        assert proxy_enabled is False
        raise KeyboardInterrupt

    monkeypatch.setattr(serve_module, "serve", interrupt_server)
    monkeypatch.setattr(ServeCommand, "line", lambda self, text: output.append(text))

    assert ServeCommand().handle() == 0
    assert any("Graphen Trace stopped." in line for line in output)
