import { afterEach, describe, expect, it, vi } from "vitest";
import { getSessionSnapshot, searchSession } from "./api";

afterEach(() => vi.unstubAllGlobals());

describe("session navigation API", () => {
  it("requests the latest page only when no fixed page is provided", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ offset: 100 }) });
    vi.stubGlobal("fetch", fetchMock);
    const signal = new AbortController().signal;
    await getSessionSnapshot("session/1", null, signal);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/sessions/session%2F1/timeline?limit=50&latest=true", { signal },
    );
    fetchMock.mockClear();
    await getSessionSnapshot("session/1", 2, signal);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/sessions/session%2F1/timeline?limit=50&offset=100", { signal },
    );
    expect(fetchMock.mock.calls.some(([path]) => path.includes("latest=true"))).toBe(false);
  });

  it("encodes search terms and requests result pages independently", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true, json: async () => ({ items: [], total: 0 }),
    });
    vi.stubGlobal("fetch", fetchMock);
    const signal = new AbortController().signal;
    await searchSession("session/1", "100% & cache", 20, signal);
    const [path, init] = fetchMock.mock.calls[0];
    const url = new URL(path, "http://localhost");
    expect(url.pathname).toBe("/api/sessions/session%2F1/search");
    expect(url.searchParams.get("q")).toBe("100% & cache");
    expect(url.searchParams.get("offset")).toBe("20");
    expect(init.signal).toBe(signal);
  });

  it("explains when the running backend still uses the old timeline contract", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true, json: async () => ({ items: [], total: 50 }),
    }));
    await expect(getSessionSnapshot("session", null, new AbortController().signal))
      .rejects.toThrow("Restart graphen-trace serve");
  });

  it("renders structured API validation errors as readable messages", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false, status: 422,
      json: async () => ({ detail: [{ loc: ["query", "offset"], msg: "Input should be a valid integer" }] }),
    }));
    await expect(searchSession("session", "cache", 0, new AbortController().signal))
      .rejects.toThrow("Input should be a valid integer");
  });
});
