"""Tests for read-only agent skill discovery."""

from pathlib import Path

from graphen_trace.services.resources import discover_resources


def test_discovery_returns_skills_with_scope_and_agent_support(tmp_path: Path) -> None:
    """Skills include scope and the providers that discover their location."""
    repository = tmp_path / "repo"
    project = repository / "packages" / "app"
    project.mkdir(parents=True)
    (repository / ".git").mkdir()
    opencode_skill = repository / ".opencode/skills/review/SKILL.md"
    opencode_skill.parent.mkdir(parents=True)
    opencode_skill.write_text(
        "---\nname: review\ndescription: Review changes\n---\n# Review safely\n",
        encoding="utf-8",
    )
    pi_skill = repository / ".pi/skills/docs/SKILL.md"
    pi_skill.parent.mkdir(parents=True)
    pi_skill.write_text("# Documentation\n\nUse clear language.\n", encoding="utf-8")
    global_skill = tmp_path / "home/.config/opencode/skills/release/SKILL.md"
    global_skill.parent.mkdir(parents=True)
    global_skill.write_text("# Release\n", encoding="utf-8")

    resources = discover_resources(project, tmp_path / "home")

    assert {(resource["scope"], resource["name"]) for resource in resources} == {
        ("project", "review"),
        ("global", "release"),
        ("project", "docs"),
    }
    review = next(resource for resource in resources if resource["name"] == "review")
    assert review["description"] == "Review changes"
    assert "# Review safely" in review["content"]
    assert review["agents"] == [{"id": "opencode", "name": "OpenCode"}]


def test_shared_agent_skill_is_returned_once_with_both_providers(
    tmp_path: Path,
) -> None:
    """A shared Agent Skills file is deduplicated and lists both providers."""
    skills = tmp_path / ".agents/skills/shared/SKILL.md"
    skills.parent.mkdir(parents=True)
    skills.write_text("# Shared skill\n", encoding="utf-8")

    resources = discover_resources(tmp_path, tmp_path / "home")

    assert len(resources) == 1
    assert resources[0]["scope"] == "project"
    assert resources[0]["agents"] == [
        {"id": "opencode", "name": "OpenCode"},
        {"id": "pi", "name": "Pi"},
    ]


def test_missing_or_unreadable_skill_directories_are_ignored(tmp_path: Path) -> None:
    """A project without supported skills returns an empty discovery result."""
    assert discover_resources(tmp_path, tmp_path / "missing-home") == []
