import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";
import { LANGUAGE_STORAGE_KEY } from "./i18n/storage";

describe("api request error handling", () => {
  it("surfaces a friendly message instead of the raw network error when the server is unreachable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("Failed to fetch"))
    );

    await expect(api.checkLink("https://youtube.com/watch?v=abc")).rejects.toThrow(
      "Can't reach the OmniFlow server. Make sure it's running, then reload this page."
    );

    vi.unstubAllGlobals();
  });

  it("still surfaces the server's own error message when the request completes with a non-OK response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        json: () => Promise.resolve({ error: "Invalid link or private video" }),
      })
    );

    await expect(api.checkLink("https://youtube.com/watch?v=abc")).rejects.toThrow(
      "Invalid link or private video"
    );

    vi.unstubAllGlobals();
  });
});

describe("api language", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("tells the server which language the user picked so its error text matches", async () => {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, "vi");
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ type: "video" }) });
    vi.stubGlobal("fetch", fetchMock);

    await api.checkLink("https://youtube.com/watch?v=abc");

    const headers = fetchMock.mock.calls[0][1].headers;
    expect(headers["X-Language"]).toBe("vi");
    expect(headers["Content-Type"]).toBe("application/json");
  });

  it("follows a language switch made after the module was loaded", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
    vi.stubGlobal("fetch", fetchMock);

    localStorage.setItem(LANGUAGE_STORAGE_KEY, "en");
    await api.checkLink("https://a.com/x");
    localStorage.setItem(LANGUAGE_STORAGE_KEY, "vi");
    await api.checkLink("https://a.com/x");

    expect(fetchMock.mock.calls[0][1].headers["X-Language"]).toBe("en");
    expect(fetchMock.mock.calls[1][1].headers["X-Language"]).toBe("vi");
  });

  it("shows the client-side connection error in Vietnamese when Vietnamese is selected", async () => {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, "vi");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    await expect(api.checkLink("https://a.com/x")).rejects.toThrow("Không kết nối được tới máy chủ OmniFlow");
  });

  it("localizes the fallback for a non-JSON response (with its status) too", async () => {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, "vi");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 404, json: () => Promise.reject(new SyntaxError("Unexpected token <")) })
    );

    await expect(api.checkLink("https://a.com/x")).rejects.toThrow("Yêu cầu thất bại (404).");
  });
});
