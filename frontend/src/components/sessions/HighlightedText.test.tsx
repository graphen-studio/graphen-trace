import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { HighlightedText } from "./HighlightedText";

describe("session search highlighting", () => {
  it("highlights every literal case-insensitive match", () => {
    const html = renderToStaticMarkup(<HighlightedText text="Cache and CACHE" query="cache" />);
    expect(html.match(/<mark /g)).toHaveLength(2);
  });

  it("treats regex syntax literally and escapes HTML", () => {
    const html = renderToStaticMarkup(<HighlightedText text="[a.*] <script>" query="[a.*]" />);
    expect(html).toContain('class="session-search-highlight">[a.*]</mark>');
    expect(html).toContain("&lt;script&gt;");
    expect(html).not.toContain("<script>");
  });

  it("preserves text for an empty search", () => {
    expect(renderToStaticMarkup(<HighlightedText text="unchanged" query=" " />)).toBe("unchanged");
  });
});
