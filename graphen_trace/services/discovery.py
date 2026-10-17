"""Read-only discovery of installed coding agents."""

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AgentInstallation:
    """Description of a detected agent executable."""

    name: str
    path: str
    version: str | None
    adapter: bool


AGENTS = {
    "opencode": True,
    "claude": False,
    "codex": False,
    "kiro": False,
    "pi": False,
}


def discover_agents() -> list[AgentInstallation]:
    """Finds known agent executables and reads their reported versions."""
    installations = []
    for name, has_adapter in AGENTS.items():
        executable = shutil.which(name)
        if executable is None:
            continue
        installations.append(
            AgentInstallation(
                name=name,
                path=str(Path(executable).resolve()),
                version=_read_version(executable),
                adapter=has_adapter,
            )
        )
    return installations


def _read_version(executable: str) -> str | None:
    """Returns a version string if the executable supports ``--version``."""
    try:
        result = subprocess.run(
            [executable, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    output = (result.stdout or result.stderr).strip().splitlines()
    return output[0] if output else None
