"""Read-only discovery of agent skills available to the local service."""

import os
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ResourceProvider:
    """Filesystem locations used by an agent to discover skills."""

    id: str
    name: str
    project_directories: tuple[str, ...]
    global_directories: tuple[str, ...]


PROVIDERS = (
    ResourceProvider(
        id="opencode",
        name="OpenCode",
        project_directories=(
            ".opencode/skills",
            ".claude/skills",
            ".agents/skills",
        ),
        global_directories=(
            ".config/opencode/skills",
            ".claude/skills",
            ".agents/skills",
        ),
    ),
    ResourceProvider(
        id="pi",
        name="Pi",
        project_directories=(".pi/skills", ".agents/skills"),
        global_directories=(".pi/agent/skills", ".agents/skills"),
    ),
)


def discover_resources(
    project_directory: Path,
    home_directory: Path | None = None,
) -> list[dict[str, object]]:
    """Returns skills found in supported project and global directories."""
    home = (home_directory or Path.home()).expanduser()
    config_home = Path(os.getenv("XDG_CONFIG_HOME", home / ".config")).expanduser()
    project_roots = _project_roots(project_directory.resolve())
    resources = {}

    for provider in PROVIDERS:
        for scope, roots, directories in (
            ("project", project_roots, provider.project_directories),
            ("global", [home], provider.global_directories),
        ):
            for root in roots:
                for directory in directories:
                    if scope == "global" and directory.startswith(".config/"):
                        skills_directory = config_home / directory.removeprefix(
                            ".config/"
                        )
                    else:
                        skills_directory = root / directory
                    for skill_file in sorted(skills_directory.rglob("SKILL.md")):
                        if not skill_file.is_file():
                            continue
                        try:
                            content = skill_file.read_text(encoding="utf-8")
                        except (OSError, UnicodeError):
                            continue
                        resolved_path = skill_file.resolve()
                        resource = resources.get(resolved_path)
                        if resource is None:
                            resource = {
                                "scope": scope,
                                "name": skill_file.parent.name,
                                "description": _description(content),
                                "path": str(resolved_path),
                                "content": content,
                                "agents": [],
                            }
                            resources[resolved_path] = resource
                        agents = resource["agents"]
                        if not any(agent["id"] == provider.id for agent in agents):
                            agents.append({"id": provider.id, "name": provider.name})

    return list(resources.values())


def _project_roots(project_directory: Path) -> list[Path]:
    """Returns the current directory and its ancestors through the git root."""
    ancestors = []
    current = project_directory
    while True:
        ancestors.append(current)
        if (current / ".git").exists():
            break
        if current.parent == current:
            return [project_directory]
        current = current.parent
    return ancestors


def _description(content: str) -> str:
    """Extracts a simple single-line YAML frontmatter description if present."""
    match = re.search(r"(?m)^description:\s*(.*?)\s*$", content)
    if match is None:
        return ""
    return match.group(1).strip("\"'")
