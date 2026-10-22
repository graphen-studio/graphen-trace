import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import AgentPicker from "./AgentPicker";

describe("agent selection after collection stops", () => {
  it("explains that selection is required without marking the agent as collecting", () => {
    const html = renderToStaticMarkup(<AgentPicker
      agents={[{ name: "opencode", path: "/bin/opencode", version: "2.0.32", adapter: true }]}
      error={null}
      notice="Collection is no longer active. Select an agent to start again."
      selectingAgent={null}
      selectedAgent={null}
      onSelect={() => undefined}
    />);
    expect(html).toContain('role="status"');
    expect(html).toContain("Collection is no longer active");
    expect(html).toContain("Start collecting");
    expect(html).toContain("No agent is collecting yet.");
    expect(html).not.toContain(">Collecting<");
  });
});
