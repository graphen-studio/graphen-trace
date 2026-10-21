import { describe, expect, it } from "vitest";
import { formatCost } from "./format";

describe("cost formatting", () => {
  it("hides floating-point noise without adding an unverified currency", () => {
    const formatted = formatCost(37.84505868000001);

    expect(formatted).toBe(
      new Intl.NumberFormat(undefined, { maximumFractionDigits: 3 }).format(
        37.84505868000001,
      ),
    );
    expect(formatted).not.toContain("000001");
    expect(formatted).not.toContain("$");
  });

  it("preserves unknown costs as unavailable", () => {
    expect(formatCost(null)).toBe("—");
  });
});
