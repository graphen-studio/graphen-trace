"""About command."""

from cleo.commands.command import Command

from graphen_trace.__version__ import __version__
from graphen_trace.commands.branding import render_banner


class AboutCommand(Command):
    """Displays product information."""

    name = "about"
    description = "Shows information about Graphen Trace"

    def handle(self) -> int:
        self.line(f"\n<fg=cyan>{render_banner()}</>")
        self.line(
            "<fg=green>Advanced tracing and observability for coding agents.</fg=green>"
        )
        self.line("Explore sessions, model usage, tool execution, and agent events.")
        self.line(
            f"\n<fg=light_gray>Version:</fg=light_gray> <info>{__version__}</info>"
        )
        return 0
