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
            self.line("\n<comment>No known agent installations detected.</comment>")
            self.line(
                "Checked commands available on PATH: OpenCode, Claude, Codex, Kiro, Pi."
            )
            return 0

        rows = []
        for agent in agents:
            adapter = (
                "<comment>Supported</comment>" if agent.adapter else "Not supported"
            )
            rows.append([agent.name.title(), agent.version or "Unknown", adapter])

        self.line("\n<info>Detected coding agents</info>")
        table = self.table()
        table.set_headers(["Agent", "Version", "Adapter support"])
        table.set_rows(rows)
        table.render()

        self.line("\n<info>Executable paths</info>")
        for agent in agents:
            self.line(f"{agent.name.title()}: {agent.path}")

        self.line("")
        self.line(
            "<comment>Read-only discovery · no collection started · "
            "no config changed.</comment>"
        )

        self.line("")
        self.line("Run <info>graphen-trace serve</info> to start passive collection.")

        return 0
