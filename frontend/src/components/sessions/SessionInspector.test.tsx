import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { SessionDetail, TimelineItem } from "../../types/session";
import SessionInspector from "./SessionInspector";

const session: SessionDetail = {
  id: "session-1", title: "Tracing", agent: "opencode", directory: "/project",
  parent_id: "parent", version: "2.0.32", source: "opencode:sqlite:v2",
  model: { id: "example", providerID: "openai" }, message_count: 2,
  usage: { input_tokens: 0, output_tokens: null, reasoning_tokens: null,
    cache_read_tokens: 1000, cache_write_tokens: null },
  usage_incomplete: ["output_tokens"], reported_cost: null, cost_incomplete: true,
  normalization_warnings: [],
};

const message: TimelineItem = {
  id: "message-1", kind: "assistant", sequence: 1, created_at: null,
  interaction_id: "user-1", interaction_source: "sequence", model: null,
  finish: null, usage: session.usage, tools: [], source: session.source,
  raw_data: { text: "<script>unsafe</script>", custom: "preserved" },
};

describe("session inspection", () => {
  it("shows session metadata before a message is selected", () => {
    const html = renderToStaticMarkup(
      <SessionInspector session={session} message={null} tool={null}
        onClose={() => undefined} onSession={() => undefined} />,
    );
    expect(html).toContain("Session details");
    expect(html).toContain("/project");
    expect(html).toContain("#/sessions/parent");
    expect(html).toContain("Missing values are not treated as zero");
  });

  it("preserves the full native message as escaped technical content", () => {
    const html = renderToStaticMarkup(
      <SessionInspector session={session} message={message} tool={null}
        onClose={() => undefined} onSession={() => undefined} />,
    );
    expect(html).toContain("Message details");
    expect(html).toContain("Complete native message");
    expect(html).toContain("preserved");
    expect(html).toContain("&lt;script&gt;");
    expect(html).not.toContain("<script>");
    expect(html).toContain("sequence");
  });

  it("shows tool arguments, output, errors, and native execution information", () => {
    const html = renderToStaticMarkup(
      <SessionInspector session={session} message={message} tool={{
        id: "call-1", name: "shell", status: "completed", duration_ms: 0,
        started_at: null, completed_at: null, exit_code: 1, child_session_id: "child",
        input: { command: "test" }, output: "Full output", error: "Native error",
      }} onClose={() => undefined} onSession={() => undefined} />,
    );
    expect(html).toContain("Tool execution");
    expect(html).toContain("completed");
    expect(html).toContain("0 ms");
    expect(html).toContain("does not necessarily mean the command succeeded");
    expect(html).toContain("Full output");
    expect(html).toContain("Native error");
    expect(html).toContain("#/sessions/child");
  });
});
