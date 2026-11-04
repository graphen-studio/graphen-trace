"""Tests for read-only agent skill discovery."""

from pathlib import Path

from graphen_trace.services.resources import discover_resources


def test_discovery_returns_skills_with_scope_and_agent_support(
    tmp_path: Path, monkeypatch
) -> None:
    """Skills include scope and the providers that discover their location."""
    monkeypatch.delenv("KIRO_HOME", raising=False)
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
    tmp_path: Path, monkeypatch
) -> None:
    """A shared Agent Skills file is deduplicated and lists both providers."""
    monkeypatch.delenv("KIRO_HOME", raising=False)
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


def test_missing_or_unreadable_skill_directories_are_ignored(
    tmp_path: Path, monkeypatch
) -> None:
    """A project without supported skills returns an empty discovery result."""
    monkeypatch.delenv("KIRO_HOME", raising=False)
    assert discover_resources(tmp_path, tmp_path / "missing-home") == []


def test_kiro_discovers_skills_steering_and_agents_files(
    tmp_path: Path, monkeypatch
) -> None:
    """Discovers Kiro's workspace/global skills and steering resources."""
    project = tmp_path / "repo"
    (project / ".git").mkdir(parents=True)
    kiro_home = tmp_path / "kiro-profile"
    monkeypatch.setenv("KIRO_HOME", str(kiro_home))

    project_skill = project / ".kiro/skills/review/SKILL.md"
    project_skill.parent.mkdir(parents=True)
    project_skill.write_text(
        "---\nname: review\ndescription: Review code safely\n---\n# Review\n",
        encoding="utf-8",
    )
    project_steering = project / ".kiro/steering/api.md"
    project_steering.parent.mkdir(parents=True)
    project_steering.write_text(
        "---\ninclusion: auto\ndescription: Follow API conventions\n---\n# API\n",
        encoding="utf-8",
    )
    project_agents = project / "src/AGENTS.md"
    project_agents.parent.mkdir()
    project_agents.write_text("# Source instructions\n", encoding="utf-8")
    vendored_agents = project / ".venv/site-packages/example/AGENTS.md"
    vendored_agents.parent.mkdir(parents=True)
    vendored_agents.write_text("# Dependency instructions\n", encoding="utf-8")

    global_skill = kiro_home / "skills/release/SKILL.md"
    global_skill.parent.mkdir(parents=True)
    global_skill.write_text("# Release workflow\n", encoding="utf-8")
    global_steering = kiro_home / "steering/team.md"
    global_steering.parent.mkdir(parents=True)
    global_steering.write_text("# Team standards\n", encoding="utf-8")
    global_agents = kiro_home / "steering/AGENTS.md"
    global_agents.write_text("# Global Kiro instructions\n", encoding="utf-8")

    ignored_default_skill = tmp_path / "home/.kiro/skills/ignored/SKILL.md"
    ignored_default_skill.parent.mkdir(parents=True)
    ignored_default_skill.write_text("# Not in KIRO_HOME\n", encoding="utf-8")

    resources = discover_resources(project, tmp_path / "home")
    kiro_resources = [
        resource
        for resource in resources
        if any(agent["id"] == "kiro" for agent in resource["agents"])
    ]

    assert {
        (resource["kind"], resource["scope"], resource["name"])
        for resource in kiro_resources
    } == {
        ("skill", "project", "review"),
        ("steering", "project", "api.md"),
        ("steering", "project", "AGENTS.md"),
        ("skill", "global", "release"),
        ("steering", "global", "team.md"),
        ("steering", "global", "AGENTS.md"),
    }
    assert (
        next(resource for resource in kiro_resources if resource["name"] == "api.md")[
            "description"
        ]
        == "Follow API conventions"
    )
    assert not any(resource["name"] == "ignored" for resource in kiro_resources)
    assert not any(
        resource["content"] == "# Dependency instructions\n"
        for resource in kiro_resources
    )


def test_kiro_home_rejects_relative_override(tmp_path: Path, monkeypatch) -> None:
    """Falls back to the default Kiro home when KIRO_HOME is not absolute."""
    project = tmp_path / "repo"
    project.mkdir()
    home = tmp_path / "home"
    monkeypatch.setenv("KIRO_HOME", "relative-kiro-home")
    default_skill = home / ".kiro/skills/default/SKILL.md"
    default_skill.parent.mkdir(parents=True)
    default_skill.write_text("# Default profile\n", encoding="utf-8")

    resources = discover_resources(project, home)

    assert any(
        resource["name"] == "default" and resource["scope"] == "global"
        for resource in resources
    )
