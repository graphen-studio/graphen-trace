import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { AgentSkill } from "../../types/api";
import { AgentResourcesContent } from "./AgentResources";

const resources: AgentSkill[] = [
  {
    scope: "project",
    name: "shared",
    description: "Review changes carefully",
    path: "/workspace/.agents/skills/shared/SKILL.md",
    content: "---\nname: shared\ndescription: Review changes carefully\nlicense: MIT\nmetadata:\n  audience: developers\n---\n# Review safely\n\n- Check the diff\n",
    agents: [
      { id: "opencode", name: "OpenCode" },
      { id: "pi", name: "Pi" },
    ],
  },
  {
    scope: "global",
    name: "docs",
    description: "Write documentation",
    path: "/home/user/.pi/agent/skills/docs/SKILL.md",
    content: "# Docs",
    agents: [{ id: "pi", name: "Pi" }],
  },
];

describe("agent resources", () => {
  it("renders discovered providers, scope, and Markdown content", () => {
    const html = renderToStaticMarkup(
      <AgentResourcesContent items={resources} loading={false} error={null} />,
    );

    expect(html).toContain("OpenCode");
    expect(html).toContain("Project");
    expect(html).toContain("Pi");
    expect(html).toContain("global");
    expect(html).toContain("OpenCode supported");
    expect(html).toContain("Pi supported");
    expect(html).toContain("Project skill");
    expect(html).toContain("Front matter");
    expect(html).toContain("YAML metadata");
    expect(html).toContain("<dt>license</dt>");
    expect(html).toContain("audience: developers");
    expect(html).toContain("<h1>Review safely</h1>");
    expect(html).toContain("Check the diff");
    expect(html).toContain("/workspace/.agents/skills/shared/SKILL.md");
    expect(html).not.toContain("<hr");
    expect(html.match(/<strong>shared<\/strong>/g)).toHaveLength(1);
  });

  it("emphasizes global origin and provider support in the selected skill", () => {
    const html = renderToStaticMarkup(
      <AgentResourcesContent items={[resources[1]]} loading={false} error={null} />,
    );

    expect(html).toContain("Global skill");
    expect(html).toContain("Pi supported");
  });

  it("renders a helpful empty state", () => {
    const html = renderToStaticMarkup(
      <AgentResourcesContent items={[]} loading={false} error={null} />,
    );

    expect(html).toContain("No skills found");
    expect(html).toContain("SKILL.md");
  });
});
