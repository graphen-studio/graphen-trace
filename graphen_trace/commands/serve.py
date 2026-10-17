"""Passive local service command."""

from cleo.commands.command import Command

from graphen_trace.config.settings import settings
from graphen_trace.services.server import serve


class ServeCommand(Command):
    """Starts passive collection, the dashboard API, and the frontend."""

    name = "serve"
    description = "Starts the local dashboard and passive collection"

    def handle(self) -> int:
        self.line(f"Dashboard: http://{settings.host}:{settings.port}")
        serve(proxy_enabled=False)
        return 0
