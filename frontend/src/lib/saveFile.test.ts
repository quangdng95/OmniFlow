import { afterEach, describe, expect, it, vi } from "vitest";
import { zipSync, strToU8 } from "fflate";
import {
  IOS_PREPARE_MAX_BYTES,
  getSavePlatform,
  prepareZipFiles,
  preparePlainFile,
  sanitizeFilename,
  saveDownloadedFile,
  sharePreparedSave,
} from "./saveFile";

const IPHONE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)";
const ANDROID_UA = "Mozilla/5.0 (Linux; Android 14; Pixel 8) Chrome/130 Mobile";
const DESKTOP_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/130";
const URL_PATH = "/api/download-file/job1";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const stubNavigator = (props: Record<string, unknown>) => vi.stubGlobal("navigator", props);

// A streaming GET answer: `size` goes into Content-Length, the body arrives in `chunks`.
const stubFetch = (data: Uint8Array, opts: { size?: number | null; chunks?: number; type?: string; status?: number; failAfterFirstChunk?: boolean } = {}) => {
  const { size = data.byteLength, chunks = 2, type = "video/mp4", status = 200, failAfterFirstChunk = false } = opts;
  const fetchMock = vi.fn((_url: string, init?: RequestInit) => {
    const parts: Uint8Array[] = [];
    const step = Math.ceil(data.byteLength / chunks);
    for (let i = 0; i < data.byteLength; i += step) parts.push(data.slice(i, i + step));
    let index = 0;
    const cancel = vi.fn().mockResolvedValue(undefined);
    const reader = {
      read: () => {
        if (init?.signal?.aborted) return Promise.reject(Object.assign(new Error("aborted"), { name: "AbortError" }));
        if (failAfterFirstChunk && index === 1) return Promise.reject(new TypeError("network error"));
        return Promise.resolve(index < parts.length ? { done: false, value: parts[index++] } : { done: true, value: undefined });
      },
      cancel,
    };
    return Promise.resolve({
      ok: status < 400,
      status,
      headers: new Headers({ "Content-Type": type, ...(size === null ? {} : { "Content-Length": String(size) }) }),
      body: { getReader: () => reader },
      blob: () => Promise.resolve(new Blob([data as BlobPart], { type })),
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
};

const clickedAnchors = (): HTMLAnchorElement[] => {
  const anchors: HTMLAnchorElement[] = [];
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
    anchors.push(this);
  });
  return anchors;
};

const bytes = (n: number) => new Uint8Array(n).fill(7);

describe("getSavePlatform", () => {
  it.each([
    ["iPhone Safari", { userAgent: IPHONE_UA }, "ios"],
    ["iPad asking for the desktop site (MacIntel + touch)", { userAgent: DESKTOP_UA, platform: "MacIntel", maxTouchPoints: 5 }, "ios"],
    ["a real Mac (MacIntel, no touch)", { userAgent: DESKTOP_UA, platform: "MacIntel", maxTouchPoints: 0 }, "desktop"],
    ["Android Chrome", { userAgent: ANDROID_UA, platform: "Linux armv8l", maxTouchPoints: 5 }, "android"],
    ["Windows", { userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", platform: "Win32" }, "desktop"],
  ])("%s", (_name, nav, expected) => {
    stubNavigator(nav);
    expect(getSavePlatform()).toBe(expected);
  });
});

describe("desktop and Android: stream straight to disk through the server URL", () => {
  it.each([
    ["desktop", { userAgent: DESKTOP_UA, platform: "MacIntel", maxTouchPoints: 0, canShare: (): boolean => true, share: vi.fn() }],
    ["android", { userAgent: ANDROID_UA, canShare: (): boolean => true, share: vi.fn() }],
  ])("%s: clicks an anchor at the URL, never fetches, never opens the share sheet", async (_name, nav) => {
    const fetchMock = stubFetch(bytes(10));
    stubNavigator(nav);
    const createObjectURL = vi.fn();
    vi.stubGlobal("URL", { createObjectURL, revokeObjectURL: vi.fn() });
    const anchors = clickedAnchors();

    const prepared = await preparePlainFile(URL_PATH, "클립: 1?.mp4");
    expect(prepared.reason).toBe("not-ios");
    expect(await saveDownloadedFile(URL_PATH, "클립: 1?.mp4")).toBe("downloaded");

    expect(fetchMock).not.toHaveBeenCalled();
    expect(createObjectURL).not.toHaveBeenCalled();
    expect((nav as { share: ReturnType<typeof vi.fn> }).share).not.toHaveBeenCalled();
    expect(anchors).toHaveLength(1);
    expect(anchors[0].getAttribute("href")).toBe(URL_PATH);
    expect(anchors[0].download).toBe("클립_ 1_.mp4");
  });

  it("streams a batch zip the same way", async () => {
    const fetchMock = stubFetch(bytes(10));
    stubNavigator({ userAgent: ANDROID_UA });
    const prepared = await prepareZipFiles(URL_PATH, "Carousel.zip");
    expect(prepared.directUrl).toBe(URL_PATH);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("iOS: prepare ahead of the tap, share inside it", () => {
  const ios = (canShare = true) => {
    const share = vi.fn().mockResolvedValue(undefined);
    stubNavigator({ userAgent: IPHONE_UA, canShare: vi.fn((): boolean => canShare), share });
    return share;
  };

  it("fetches with progress into a File with the right type and Unicode name, then shares it exactly once", async () => {
    stubFetch(bytes(100), { chunks: 4 });
    const share = ios();
    const progress: number[] = [];

    const prepared = await preparePlainFile(URL_PATH, "Bài hát 한국어.mp4", { onProgress: (p) => progress.push(p) });
    expect(share).not.toHaveBeenCalled(); // nothing is shared until the tap
    expect(prepared.directUrl).toBeUndefined();
    expect(prepared.files).toHaveLength(1);
    expect(prepared.files[0].type).toBe("video/mp4");
    expect(prepared.files[0].name).toBe("Bài hát 한국어.mp4");
    expect(progress.length).toBeGreaterThan(1);
    expect(progress[progress.length - 1]).toBe(100);
    expect(progress.every((p, i) => i === 0 || p >= progress[i - 1])).toBe(true);

    // The tap: share() must be called synchronously, before the returned promise settles.
    const pending = sharePreparedSave(prepared);
    expect(share).toHaveBeenCalledTimes(1);
    expect(await pending).toBe("shared");
    expect(share.mock.calls[0][0].files).toHaveLength(1);
  });

  it("falls back to the server URL for a file over the size limit and never reads its body", async () => {
    const fetchMock = stubFetch(bytes(10), { size: IOS_PREPARE_MAX_BYTES + 1 });
    const share = ios();
    const anchors = clickedAnchors();

    const prepared = await preparePlainFile(URL_PATH, "big.mp4");
    expect(prepared.reason).toBe("too-big");
    expect(prepared.directUrl).toBe(URL_PATH);
    expect(await sharePreparedSave(prepared)).toBe("downloaded");
    expect(share).not.toHaveBeenCalled();
    expect(anchors[0].getAttribute("href")).toBe(URL_PATH);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("falls back to the server URL when canShare says the file cannot be shared", async () => {
    stubFetch(bytes(10));
    const share = ios(false);
    clickedAnchors();
    const prepared = await preparePlainFile(URL_PATH, "clip.mp4");
    expect(prepared.reason).toBe("cannot-share");
    expect(await sharePreparedSave(prepared)).toBe("downloaded");
    expect(share).not.toHaveBeenCalled();
  });

  it("falls back to the server URL when the page runs out of memory / the stream dies mid-way", async () => {
    stubFetch(bytes(100), { chunks: 4, failAfterFirstChunk: true });
    ios();
    const prepared = await preparePlainFile(URL_PATH, "clip.mp4");
    expect(prepared.reason).toBe("no-memory");
  });

  it("surfaces an HTTP error instead of hiding it", async () => {
    stubFetch(bytes(1), { status: 404 });
    ios();
    await expect(preparePlainFile(URL_PATH, "clip.mp4")).rejects.toThrow("Failed to fetch file (404)");
  });

  it("can be cancelled: an aborted preparation rejects with AbortError and shares nothing", async () => {
    stubFetch(bytes(100), { chunks: 4 });
    const share = ios();
    const controller = new AbortController();
    controller.abort();
    await expect(preparePlainFile(URL_PATH, "clip.mp4", { signal: controller.signal })).rejects.toMatchObject({ name: "AbortError" });
    expect(share).not.toHaveBeenCalled();
  });

  it("backing out of the share sheet rejects with AbortError for the caller to ignore", async () => {
    stubFetch(bytes(10));
    const share = vi.fn().mockRejectedValue(Object.assign(new Error("cancel"), { name: "AbortError" }));
    stubNavigator({ userAgent: IPHONE_UA, canShare: (): boolean => true, share });
    const prepared = await preparePlainFile(URL_PATH, "clip.mp4");
    await expect(sharePreparedSave(prepared)).rejects.toMatchObject({ name: "AbortError" });
  });

  it("unzips a small batch archive and shares each entry as its own file", async () => {
    const zipped = zipSync({ "photo1.jpg": strToU8("a"), "photo2.jpg": strToU8("b") });
    stubFetch(zipped, { type: "application/zip" });
    const share = ios();

    const prepared = await prepareZipFiles(URL_PATH, "Carousel.zip");
    expect(await sharePreparedSave(prepared)).toBe("shared");
    const files = share.mock.calls[0][0].files as File[];
    expect(files.map((f) => f.name).sort()).toEqual(["photo1.jpg", "photo2.jpg"]);
    expect(files[0].type).toBe("image/jpeg");
  });

  it("a batch zip over the limit goes to Files by URL", async () => {
    stubFetch(bytes(10), { size: IOS_PREPARE_MAX_BYTES + 1 });
    ios();
    expect((await prepareZipFiles(URL_PATH, "Big.zip")).reason).toBe("too-big");
  });
});

describe("helpers", () => {
  it("sanitizes forbidden characters but keeps Unicode titles", () => {
    expect(sanitizeFilename('안녕 세계: "a/b"?.mp4')).toBe("안녕 세계_ _a_b__.mp4");
    expect(sanitizeFilename("...")).toBe("download");
  });

  it("revokes a blob URL only after the delayed fallback download starts", async () => {
    vi.useFakeTimers();
    try {
      stubNavigator({ userAgent: DESKTOP_UA });
      const revoke = vi.fn();
      vi.stubGlobal("URL", { createObjectURL: vi.fn().mockReturnValue("blob:fake"), revokeObjectURL: revoke });
      clickedAnchors();
      await sharePreparedSave({ files: [], fallbackBlob: new Blob(["x"]), fallbackFilename: "clip.zip" });
      expect(revoke).not.toHaveBeenCalled();
      vi.runAllTimers();
      expect(revoke).toHaveBeenCalledWith("blob:fake");
    } finally {
      vi.useRealTimers();
    }
  });
});
