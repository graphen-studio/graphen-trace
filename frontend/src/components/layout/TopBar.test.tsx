import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import TopBar from "./TopBar";

describe("top bar controls", () => {
  it("shows a compact agent selector and icon-only repository and theme controls", () => {
    const html = renderToStaticMarkup(
      <TopBar
        theme="dark"
        selectedAgent="opencode"
        collectionState="collecting"
        onChangeAgent={() => undefined}
        onToggleTheme={() => undefined}
      />,
    );

    expect(html).toContain("OpenCode");
    expect(html).not.toContain("<small");
    expect(html).toContain("Change agent");
    expect(html).toContain("https://github.com/graphen-studio/graphen-trace");
    expect(html).toContain('class="topbar-icon-button"');
    expect(html).not.toContain(">GitHub<");
    expect(html).toContain("Switch to light mode");
  });

  it("uses the light wordmark and offers the dark theme action", () => {
    const html = renderToStaticMarkup(
      <TopBar
        theme="light"
        selectedAgent={null}
        collectionState={undefined}
        onChangeAgent={() => undefined}
        onToggleTheme={() => undefined}
      />,
    );

    expect(html).toContain("/logo-text-light.png");
    expect(html).toContain("Switch to dark mode");
    expect(html).not.toContain("Change agent");
  });
});
