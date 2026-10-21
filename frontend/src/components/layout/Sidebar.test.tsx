import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import Sidebar from "./Sidebar";

describe("sidebar navigation", () => {
  it("keeps planned areas visible but unavailable", () => {
    const html = renderToStaticMarkup(
      <Sidebar
        active
        sessionsEnabled
        serviceStatus="connected"
        onSessions={() => undefined}
      />,
    );

    expect(html).toContain('aria-label="Main navigation"');
    expect(html).toContain('aria-current="page"');
    expect(html).toContain("Agent resources");
    expect(html).toContain("Skills · Steerings · Hooks");
    expect(html).toContain("Live proxy");
    expect(html).toContain("Dashboards");
    expect(html.match(/disabled=""/g)).toHaveLength(3);
  });
});
