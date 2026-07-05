import { describe, expect, it, vi } from "vitest";
import { api } from "./api";

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
