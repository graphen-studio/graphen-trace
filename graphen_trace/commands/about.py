"""About command."""

from cleo.commands.command import Command

from graphen_trace.__version__ import __version__


class AboutCommand(Command):
    """Displays product information."""

    name = "about"
    description = "Shows information about Graphen Trace"

    def handle(self) -> int:
        self.line(f"<info>Graphen Trace</info> {__version__}")
        self.line("A local dashboard for observing coding agent activity.")
        return 0
