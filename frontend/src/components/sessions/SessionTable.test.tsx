import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import SessionTable from "./SessionTable";
import type { SessionSummary } from "../../types/api";
import { formatCount } from "../../utils/format";

describe("session table", () => {
  it("shows session details and formatted native token counts", () => {
    const session: SessionSummary = {
      id: "session/1",
      title: "Implement tracing",
      directory: "/work/project",
      model: { providerID: "openai", id: "gpt-example" },
      updated_at: "2026-10-20T12:00:00Z",
      message_count: 1234,
      source: "opencode:sqlite:v2",
      usage: { input_tokens: 1234567, output_tokens: 98765 },
    };

    const html = renderToStaticMarkup(<SessionTable sessions={[session]} />);
    expect(html).toContain("Implement tracing");
    expect(html).toContain("/work/project");
    expect(html).toContain("gpt-example");
    expect(html).toContain(`>${formatCount(1234)}<`);
    expect(html).toContain(`>${formatCount(1234567)}<`);
    expect(html).toContain("#/sessions/session%2F1");
    expect(html).toContain("Search sessions by title, project, or model");
  });

  it("shows an empty result when there are no loaded sessions", () => {
    const html = renderToStaticMarkup(<SessionTable sessions={[]} />);
    expect(html).toContain("Waiting for agent activity");
  });
});
