"""Installed-agent discovery command."""

from cleo.commands.command import Command

from graphen_trace.services.discovery import discover_agents


class DiscoverCommand(Command):
    """Lists installed agents and available capture adapters."""

    name = "discover"
    description = "Detects installed coding agents without modifying them"

    def handle(self) -> int:
        agents = discover_agents()
        if not agents:
            self.line("No supported agent installations detected.")
            return 0

        self.line("<info>Installed agents</info>")
        for agent in agents:
            version = f" ({agent.version})" if agent.version else ""
            adapter = "capture adapter available" if agent.adapter else "no adapter yet"
            self.line(f"- {agent.name}{version}: {adapter}")
            if agent.path:
                self.line(f"  Path: {agent.path}")
        self.line(
            "Discovery is read-only; only OpenCode capture is planned for the MVP."
        )
        return 0
