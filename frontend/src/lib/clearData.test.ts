import { afterEach, describe, expect, it, vi } from "vitest";
import { clearBrowserData } from "./clearData";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  localStorage.clear();
  sessionStorage.clear();
});

describe("clearBrowserData", () => {
  it("empties localStorage, sessionStorage, Cache Storage and the cookies the page can see", async () => {
    localStorage.setItem("omniflow-history", "[1]");
    localStorage.setItem("omniflow-language", "vi");
    sessionStorage.setItem("x", "1");
    document.cookie = "omniflow-language=vi; path=/";
    const deleted: string[] = [];
    vi.stubGlobal("caches", { keys: () => Promise.resolve(["a", "b"]), delete: (n: string) => (deleted.push(n), Promise.resolve(true)) });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));

    const report = await clearBrowserData();

    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
    expect(deleted).toEqual(["a", "b"]);
    expect(document.cookie).not.toContain("omniflow-language");
    expect(report).toMatchObject({ storageKeys: 3, cacheStores: 2 });
  });

  it("refreshes the core files in the HTTP cache (cache: reload) before it drops anything", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    await clearBrowserData();
    const urls = fetchMock.mock.calls.map(([url]) => url);
    expect(urls).toEqual(expect.arrayContaining(["/", "/manifest.webmanifest?v=4", "/apple-touch-icon.png?v=4"]));
    expect(fetchMock.mock.calls.every(([, init]) => init?.cache === "reload")).toBe(true);
  });

  it("keeps going when one storage refuses (private mode) or the network is down", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    vi.stubGlobal("caches", { keys: () => Promise.reject(new Error("blocked")), delete: vi.fn() });
    localStorage.setItem("k", "v");
    await expect(clearBrowserData()).resolves.toBeDefined();
    expect(localStorage.length).toBe(0);
  });
});
