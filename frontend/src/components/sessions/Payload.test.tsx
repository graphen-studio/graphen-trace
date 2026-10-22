import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { Payload } from "./Payload";

describe("JSON payload presentation", () => {
  it("indents structured JSON and highlights keys and value types safely", () => {
    const html = renderToStaticMarkup(<Payload label="Arguments" value={{
      command: "<script>unsafe</script>", count: 12, active: true, result: null,
      nested: { text: 'quote: "test"' },
    }} />);
    expect(html).toContain('class="json-key"');
    expect(html).toContain('class="json-string"');
    expect(html).toContain('class="json-number"');
    expect(html).toContain('class="json-boolean"');
    expect(html).toContain('class="json-null"');
    expect(html).toContain("\n  ");
    expect(html).toContain("&lt;script&gt;");
    expect(html).not.toContain("<script>");
  });

  it("keeps text output intact without interpreting it as JSON or HTML", () => {
    const text = 'Text output <b>literal</b> 12345';
    const html = renderToStaticMarkup(<Payload label="Result" value={text} />);
    expect(html).toContain("Text output &lt;b&gt;literal&lt;/b&gt; 12345");
    expect(html).not.toContain('class="json-payload"');
  });
});
