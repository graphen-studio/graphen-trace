"""About command."""

from cleo.commands.command import Command
from pyfiglet import Figlet

from graphen_trace.__version__ import __version__


class AboutCommand(Command):
    """Displays product information."""

    name = "about"
    description = "Shows information about Graphen Trace"

    def handle(self) -> int:
        title = Figlet(font="slant").renderText("Graphen Trace")
        self.line(f"\n<fg=cyan>{title}</>")
        self.line(
            "<fg=green>Advanced tracing and observability for coding agents.</fg=green>"
        )
        self.line("Explore sessions, model usage, tool execution, and agent events.")
        self.line(
            f"\n<fg=light_gray>Version:</fg=light_gray> <info>{__version__}</info>"
        )
        return 0
