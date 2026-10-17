import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { Payload, Timeline, type TimelineItem } from "./SessionDetails";

describe("session timeline", () => {
  it("shows native tool states without interpreting completed as success", () => {
    const item: TimelineItem = {
      id: "message-1", kind: "assistant", sequence: 1, created_at: null,
      interaction_id: "user-1", interaction_source: "sequence",
      model: { providerID: "openai", id: "example" }, finish: "tool-calls",
      usage: { input_tokens: 0, output_tokens: null, reasoning_tokens: null,
        cache_read_tokens: null, cache_write_tokens: null },
      source: "opencode:sqlite:v2",
      tools: [{ id: "tool-1", name: "bash", status: "completed", exit_code: 1,
        started_at: null, completed_at: null, duration_ms: null, child_session_id: "child" }],
    };
    const html = renderToStaticMarkup(<Timeline items={[item]} />);
    expect(html).toContain("completed");
    expect(html).toContain("Exit code: 1");
    expect(html).toContain("Input: 0");
    expect(html).toContain("Output: —");
    expect(html).toContain("#/sessions/child");
    expect(html).not.toContain("success");
  });

  it("escapes source labels instead of interpreting them as HTML", () => {
    const html = renderToStaticMarkup(<Timeline items={[{
      id: "m1", kind: "<script>unsafe</script>", sequence: 1,
      created_at: null, interaction_id: null, interaction_source: null,
      model: null, finish: null, usage: null, tools: [], source: "sqlite",
    }]} />);
    expect(html).toContain("&lt;script&gt;");
    expect(html).not.toContain("<script>");
  });

  it("shows full execution content as escaped text without truncation", () => {
    const text = "private source content ".repeat(1000) + "<script>unsafe</script>";
    const html = renderToStaticMarkup(<Payload label="Result" value={text} />);
    expect(html).toContain("private source content ".repeat(1000));
    expect(html).toContain("&lt;script&gt;");
    expect(html).not.toContain("<script>");
  });
});
