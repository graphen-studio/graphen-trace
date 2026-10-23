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

  it("passes Pi selection to session detail and timeline requests", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ offset: 0 }),
    });
    vi.stubGlobal("fetch", fetchMock);
    await getSessionSnapshot("pi-session", null, new AbortController().signal, "pi");

    const paths = fetchMock.mock.calls.map(([path]) => path as string);
    expect(paths).toContain("/api/sessions/pi-session?agent=pi");
    expect(paths).toContain(
      "/api/sessions/pi-session/timeline?limit=50&latest=true&agent=pi",
    );
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

  it("includes the selected agent when searching a Pi session", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [], total: 0 }),
    });
    vi.stubGlobal("fetch", fetchMock);
    await searchSession("pi-session", "tool output", 0, new AbortController().signal, "pi");
    const url = new URL(fetchMock.mock.calls[0][0], "http://localhost");

    expect(url.searchParams.get("agent")).toBe("pi");
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
