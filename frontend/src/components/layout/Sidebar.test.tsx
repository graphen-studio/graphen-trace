import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import Sidebar from "./Sidebar";

describe("sidebar navigation", () => {
  it("enables agent resources and keeps future areas unavailable", () => {
    const html = renderToStaticMarkup(
      <Sidebar
        activePage="sessions"
        sessionsEnabled
        serviceStatus="connected"
        onSessions={() => undefined}
        onResources={() => undefined}
      />,
    );

    expect(html).toContain('aria-label="Main navigation"');
    expect(html).toContain('aria-current="page"');
    expect(html).toContain("Agent resources");
    expect(html).toContain("Skills by agent and scope");
    expect(html).toContain("Live proxy");
    expect(html).toContain("Dashboards");
    expect(html.match(/disabled=""/g)).toHaveLength(2);
  });
});
