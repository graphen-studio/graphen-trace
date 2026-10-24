"""Passive local service command."""

from cleo.commands.command import Command

from graphen_trace.commands.branding import render_banner
from graphen_trace.config.settings import settings
from graphen_trace.services.server import serve


class ServeCommand(Command):
    """Starts passive collection, the dashboard API, and the frontend."""

    name = "serve"
    description = "Starts the local dashboard and passive collection"

    def handle(self) -> int:
        self.line(f"\n<fg=cyan>{render_banner()}</>")
        self.line("<info>Starting Graphen Trace</info>")
        self.line(f"Dashboard: http://{settings.host}:{settings.port}")
        self.line("Press Ctrl+C to stop.\n")
        try:
            serve(proxy_enabled=False)
        except KeyboardInterrupt:
            self.line("\n<info>Graphen Trace stopped.</info>")
        return 0
