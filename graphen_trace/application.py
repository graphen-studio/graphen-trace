"""Cleo application and command registration."""

from cleo.application import Application as BaseApplication

from graphen_trace.__version__ import __version__
from graphen_trace.commands.about import AboutCommand
from graphen_trace.commands.discover import DiscoverCommand
from graphen_trace.commands.run import RunOpenCodeCommand
from graphen_trace.commands.serve import ServeCommand


class Application(BaseApplication):
    """Graphen Trace CLI application."""

    def __init__(self) -> None:
        super().__init__("graphen-trace", __version__)
        for command in (
            AboutCommand(),
            DiscoverCommand(),
            ServeCommand(),
            RunOpenCodeCommand(),
        ):
            self.add(command)
