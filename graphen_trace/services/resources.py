"""Read-only discovery of agent skills available to the local service."""

import os
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ResourceProvider:
    """Filesystem locations used by an agent to discover local resources."""

    id: str
    name: str
    project_directories: tuple[str, ...]
    global_directories: tuple[str, ...]
    project_steering_directories: tuple[str, ...] = ()
    global_steering_directories: tuple[str, ...] = ()
    project_instruction_files: tuple[str, ...] = ()


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
    ResourceProvider(
        id="kiro",
        name="Kiro",
        project_directories=(".kiro/skills",),
        global_directories=(".kiro/skills",),
        project_steering_directories=(".kiro/steering",),
        global_steering_directories=(".kiro/steering",),
        project_instruction_files=("AGENTS.md",),
    ),
)
EXCLUDED_PROJECT_DIRECTORIES = {
    ".git",
    ".mypy_cache",
    ".next",
    ".pytest_cache",
    ".tox",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "vendor",
    "venv",
    ".venv",
}


def discover_resources(
    project_directory: Path,
    home_directory: Path | None = None,
) -> list[dict[str, object]]:
    """Returns resources found in supported project and global locations."""
    home = (home_directory or Path.home()).expanduser()
    config_home = Path(os.getenv("XDG_CONFIG_HOME", home / ".config")).expanduser()
    kiro_home = kiro_home_directory(home)
    project_roots = project_roots_for(project_directory.resolve())
    resources = {}

    for provider in PROVIDERS:
        for scope, roots, skill_directories, steering_directories in (
            (
                "project",
                project_roots,
                provider.project_directories,
                provider.project_steering_directories,
            ),
            (
                "global",
                [home],
                provider.global_directories,
                provider.global_steering_directories,
            ),
        ):
            for root in roots:
                for directory in skill_directories:
                    resource_directory = resolve_resource_directory(
                        root, directory, scope, config_home, kiro_home
                    )
                    for resource_file in sorted(resource_directory.rglob("SKILL.md")):
                        add_resource(resources, provider, scope, resource_file, "skill")
                for directory in steering_directories:
                    resource_directory = resolve_resource_directory(
                        root, directory, scope, config_home, kiro_home
                    )
                    for resource_file in sorted(resource_directory.rglob("*.md")):
                        add_resource(
                            resources, provider, scope, resource_file, "steering"
                        )

        if provider.project_instruction_files:
            for filename in provider.project_instruction_files:
                for resource_file in find_project_instruction_files(
                    project_roots[-1], filename
                ):
                    add_resource(
                        resources, provider, "project", resource_file, "steering"
                    )

    return list(resources.values())


def resolve_resource_directory(
    root: Path,
    directory: str,
    scope: str,
    config_home: Path,
    kiro_home: Path,
) -> Path:
    """Resolves provider directories for project and global resource scopes."""
    if scope != "global":
        return root / directory
    if directory.startswith(".config/"):
        return config_home / directory.removeprefix(".config/")
    if directory.startswith(".kiro/"):
        return kiro_home / directory.removeprefix(".kiro/")
    return root / directory


def kiro_home_directory(home: Path) -> Path:
    """Resolves Kiro's global root while ignoring invalid KIRO_HOME values."""
    configured_home = os.getenv("KIRO_HOME")
    if not configured_home:
        return home / ".kiro"
    candidate = Path(configured_home).expanduser()
    resolved_home = home.resolve()
    if not candidate.is_absolute():
        return resolved_home / ".kiro"
    candidate = candidate.resolve()
    if candidate == Path(candidate.anchor) or candidate in (
        resolved_home,
        *resolved_home.parents,
    ):
        return resolved_home / ".kiro"
    return candidate


def find_project_instruction_files(root: Path, filename: str) -> list[Path]:
    """Finds workspace instructions while skipping generated/vendor trees."""
    matches = []
    for current, directories, files in os.walk(root):
        directories[:] = sorted(
            directory
            for directory in directories
            if directory not in EXCLUDED_PROJECT_DIRECTORIES
        )
        if filename in files:
            matches.append(Path(current) / filename)
    return sorted(matches)


def add_resource(
    resources: dict[Path, dict[str, object]],
    provider: ResourceProvider,
    scope: str,
    resource_file: Path,
    kind: str,
) -> None:
    """Adds a readable resource once and accumulates compatible providers."""
    if not resource_file.is_file():
        return
    try:
        content = resource_file.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return

    resolved_path = resource_file.resolve()
    resource = resources.get(resolved_path)
    if resource is None:
        resource = {
            "kind": kind,
            "scope": scope,
            "name": (
                resource_file.parent.name if kind == "skill" else resource_file.name
            ),
            "description": resource_description(content),
            "path": str(resolved_path),
            "content": content,
            "agents": [],
        }
        resources[resolved_path] = resource
    agents = resource["agents"]
    if not any(agent["id"] == provider.id for agent in agents):
        agents.append({"id": provider.id, "name": provider.name})


def project_roots_for(project_directory: Path) -> list[Path]:
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


def resource_description(content: str) -> str:
    """Extracts a simple single-line YAML frontmatter description if present."""
    frontmatter = re.match(
        r"^\ufeff?---\r?\n([\s\S]*?)\r?\n(?:---|\.\.\.)[ \t]*(?:\r?\n|$)",
        content,
    )
    if frontmatter is None:
        return ""
    match = re.search(r"(?m)^description:\s*(.*?)\s*$", frontmatter.group(1))
    if match is None:
        return ""
    return match.group(1).strip("\"'")
