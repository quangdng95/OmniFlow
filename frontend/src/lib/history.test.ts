import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  HISTORY_LIMIT,
  HISTORY_STORAGE_KEY,
  clearHistory,
  loadHistory,
  recordDownload,
  removeHistoryEntry,
} from "./history";

const entry = (n: number) => ({
  url: `https://example.com/v/${n}`,
  title: `Video ${n}`,
  platform: "YouTube" as const,
  thumbnail: null,
});

beforeEach(() => {
  localStorage.clear();
});

describe("download history", () => {
  it("starts empty", () => {
    expect(loadHistory()).toEqual([]);
  });

  it("lists the newest download first", () => {
    recordDownload(entry(1));
    recordDownload(entry(2));
    expect(loadHistory().map((e) => e.title)).toEqual(["Video 2", "Video 1"]);
  });

  it("keeps only the 10 most recent", () => {
    for (let n = 1; n <= 12; n += 1) recordDownload(entry(n));
    const saved = loadHistory();
    expect(saved).toHaveLength(HISTORY_LIMIT);
    expect(saved[0].title).toBe("Video 12");
    expect(saved[HISTORY_LIMIT - 1].title).toBe("Video 3");
  });

  it("moves a re-downloaded link to the top instead of listing it twice", () => {
    recordDownload(entry(1));
    recordDownload(entry(2));
    recordDownload({ ...entry(1), title: "Video 1 (renamed)" });
    const saved = loadHistory();
    expect(saved.map((e) => e.title)).toEqual(["Video 1 (renamed)", "Video 2"]);
  });

  it("ignores a blank URL", () => {
    recordDownload({ ...entry(1), url: "   " });
    expect(loadHistory()).toEqual([]);
  });

  it("removes one entry and can clear everything", () => {
    recordDownload(entry(1));
    recordDownload(entry(2));
    expect(removeHistoryEntry(entry(1).url).map((e) => e.title)).toEqual(["Video 2"]);
    clearHistory();
    expect(loadHistory()).toEqual([]);
  });

  it("survives corrupted storage instead of throwing", () => {
    localStorage.setItem(HISTORY_STORAGE_KEY, "{not json");
    expect(loadHistory()).toEqual([]);
    localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify([{ url: 5 }, { ...entry(1), downloadedAt: 1 }]));
    expect(loadHistory().map((e) => e.title)).toEqual(["Video 1"]);
  });

  it("does not throw when storage is unavailable", () => {
    const spy = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(() => recordDownload(entry(1))).not.toThrow();
    spy.mockRestore();
  });
});
