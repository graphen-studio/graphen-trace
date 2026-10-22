import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { Payload, Timeline, type TimelineItem } from "./SessionDetails";
import { MarkdownContent } from "./SessionTimeline";

describe("session timeline", () => {
  it("renders common Markdown structures and leaves raw HTML inert", () => {
    const html = renderToStaticMarkup(<MarkdownContent source={[
      "## Change summary",
      "",
      "- **Cache** reuse",
      "- `tokens`",
      "",
      "| Metric | Value |",
      "| --- | ---: |",
      "| Input | 123 |",
      "",
      "```python",
      "print('safe')",
      "```",
      "",
      "<script>alert('unsafe')</script>",
    ].join("\n")} />);

    expect(html).toContain("<h2>Change summary</h2>");
    expect(html).toContain("<strong>Cache</strong>");
    expect(html).toContain("<table>");
    expect(html).toContain("<pre><code class=\"language-python\">print(&#x27;safe&#x27;)");
    expect(html).not.toContain("<script>");
    expect(html).not.toContain("alert('unsafe')");
  });

  it("keeps session search highlighting inside rendered Markdown", () => {
    const html = renderToStaticMarkup(
      <MarkdownContent source="**Cache** is reused" query="cache" />,
    );
    expect(html).toContain("<strong><mark class=\"session-search-highlight\">Cache</mark></strong>");
  });

  it("renders text reasoning as collapsed Markdown without enabling raw HTML", () => {
    const html = renderToStaticMarkup(<Timeline items={[{
      id: "reasoning-message", kind: "assistant", sequence: 1,
      created_at: null, interaction_id: null, interaction_source: null,
      model: null, finish: null, usage: null, tools: [], source: "sqlite",
      raw_data: { content: [{
        type: "reasoning",
        text: "## Hypothesis\n\n- **Reuse** context\n\n<script>alert('unsafe')</script>",
      }] },
    }]} />);

    expect(html).toContain("<summary>Reasoning</summary>");
    const detailsTag = html.match(/<details\b[^>]*reasoning-payload[^>]*>/)?.[0] ?? "";
    expect(detailsTag).not.toContain("open");
    expect(html).toContain("<h2>Hypothesis</h2>");
    expect(html).toContain("<strong>Reuse</strong>");
    expect(html).not.toContain("<script>");
  });

  it("does not render empty or whitespace-only reasoning collapses", () => {
    const html = renderToStaticMarkup(<Timeline items={[{
      id: "empty-reasoning", kind: "assistant", sequence: 1,
      created_at: null, interaction_id: null, interaction_source: null,
      model: null, finish: null, usage: null, tools: [], source: "sqlite",
      raw_data: { content: [
        { type: "reasoning", text: "" },
        { type: "reasoning", text: " \n  " },
        { type: "reasoning" },
      ] },
    }]} />);
    expect(html).not.toContain("<summary>Reasoning</summary>");
  });

  it("marks the selected message and offers an explicit inspection action", () => {
    const html = renderToStaticMarkup(<Timeline items={[{
      id: "selected", kind: "user", sequence: 1, created_at: null,
      interaction_id: null, interaction_source: null, model: null,
      finish: null, usage: null, tools: [], source: "sqlite",
      raw_data: { text: "Keep the conversation readable" },
    }]} selection={{ messageId: "selected" }} onInspect={() => undefined} />);
    expect(html).toContain("is-inspected");
    expect(html).toContain('aria-pressed="true"');
    expect(html).toContain("Keep the conversation readable");
  });

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

  it("shows compatibility warnings and preserves unrecognized payloads", () => {
    const html = renderToStaticMarkup(<Timeline items={[{
      id: "m1", kind: "assistant", sequence: null, created_at: null,
      interaction_id: null, interaction_source: null, model: null, finish: null,
      usage: null, tools: [], source: "sqlite", raw_payload: "opaque content",
      normalization_warnings: ["Unknown tokens format; original payload preserved"],
    }]} />);
    expect(html).toContain("Unknown order");
    expect(html).toContain("Unknown tokens format");
    expect(html).toContain("opaque content");
  });
});
