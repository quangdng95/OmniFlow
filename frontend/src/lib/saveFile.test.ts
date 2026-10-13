import { afterEach, describe, expect, it, vi } from "vitest";
import { zipSync, strToU8 } from "fflate";
import {
  SHARE_SHEET_MAX_BYTES,
  sanitizeFilename,
  saveDownloadedFile,
  saveDownloadedZipAsFiles,
  shouldUseShareSheet,
} from "./saveFile";

const MOBILE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)";
const DESKTOP_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/130";
const URL_PATH = "/api/download-file/job1";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const stubPointer = (coarse: boolean): void => {
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: coarse && query.includes("coarse") }));
};

const stubUrl = () => {
  const revoke = vi.fn();
  vi.stubGlobal("URL", { createObjectURL: vi.fn().mockReturnValue("blob:fake"), revokeObjectURL: revoke });
  return revoke;
};

// HEAD answers with a Content-Length of `size`; GET answers with the blob.
const stubFetch = (blob: Blob, size: number | null = blob.size) => {
  const fetchMock = vi.fn((_url: string, init?: RequestInit) =>
    Promise.resolve(
      init?.method === "HEAD"
        ? { ok: true, headers: new Headers(size === null ? {} : { "Content-Length": String(size) }) }
        : { ok: true, blob: () => Promise.resolve(blob) }
    )
  );
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

const videoBlob = () => new Blob(["fake bytes"], { type: "video/mp4" });

describe("desktop: stream straight to disk", () => {
  it("clicks an anchor at the server URL without fetching anything or opening the share sheet", async () => {
    const fetchMock = stubFetch(videoBlob());
    stubPointer(false);
    const share = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { userAgent: DESKTOP_UA, canShare: () => true, share });
    const createObjectURL = vi.fn();
    vi.stubGlobal("URL", { createObjectURL, revokeObjectURL: vi.fn() });
    const anchors = clickedAnchors();

    const result = await saveDownloadedFile(URL_PATH, "클립: 1?.mp4");

    expect(result).toBe("downloaded");
    expect(fetchMock).not.toHaveBeenCalled();
    expect(createObjectURL).not.toHaveBeenCalled();
    expect(share).not.toHaveBeenCalled();
    expect(anchors).toHaveLength(1);
    expect(anchors[0].getAttribute("href")).toBe(URL_PATH);
    expect(anchors[0].download).toBe("클립_ 1_.mp4");
  });

  it("streams a batch zip the same way", async () => {
    const fetchMock = stubFetch(videoBlob());
    stubPointer(false);
    vi.stubGlobal("navigator", { userAgent: DESKTOP_UA });
    const anchors = clickedAnchors();

    expect(await saveDownloadedZipAsFiles(URL_PATH, "Carousel.zip")).toBe("downloaded");
    expect(fetchMock).not.toHaveBeenCalled();
    expect(anchors[0].getAttribute("href")).toBe(URL_PATH);
  });
});

describe("mobile", () => {
  const mobile = (canShare: boolean) => {
    stubPointer(true);
    const share = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { userAgent: MOBILE_UA, canShare: () => canShare, share });
    return share;
  };

  it("shares a small file via the share sheet", async () => {
    stubFetch(videoBlob());
    const share = mobile(true);

    expect(await saveDownloadedFile(URL_PATH, "clip.mp4")).toBe("shared");
    const files = share.mock.calls[0][0].files as File[];
    expect(files.map((f) => f.name)).toEqual(["clip.mp4"]);
  });

  it("streams a file over the size limit instead of buffering it", async () => {
    const fetchMock = stubFetch(videoBlob(), SHARE_SHEET_MAX_BYTES + 1);
    const share = mobile(true);
    const anchors = clickedAnchors();

    expect(await saveDownloadedFile(URL_PATH, "big.mp4")).toBe("downloaded");
    expect(share).not.toHaveBeenCalled();
    expect(fetchMock.mock.calls.every(([, init]) => init?.method === "HEAD")).toBe(true);
    expect(anchors[0].getAttribute("href")).toBe(URL_PATH);
  });

  it("streams when the size is unknown", async () => {
    stubFetch(videoBlob(), null);
    const share = mobile(true);
    clickedAnchors();

    expect(await saveDownloadedFile(URL_PATH, "clip.mp4")).toBe("downloaded");
    expect(share).not.toHaveBeenCalled();
  });

  it("streams when the size probe fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network")));
    mobile(true);
    const anchors = clickedAnchors();

    expect(await saveDownloadedFile(URL_PATH, "clip.mp4")).toBe("downloaded");
    expect(anchors).toHaveLength(1);
  });

  it("falls back to a blob download when canShare says no", async () => {
    stubFetch(videoBlob());
    const share = mobile(false);
    stubUrl();
    const anchors = clickedAnchors();

    expect(await saveDownloadedFile(URL_PATH, "clip.mp4")).toBe("downloaded");
    expect(share).not.toHaveBeenCalled();
    expect(anchors[0].getAttribute("href")).toBe("blob:fake");
  });

  it("throws a friendly error when fetching the small file fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((_url: string, init?: RequestInit) =>
        Promise.resolve(
          init?.method === "HEAD" ? { ok: true, headers: new Headers({ "Content-Length": "10" }) } : { ok: false, status: 404 }
        )
      )
    );
    mobile(true);

    await expect(saveDownloadedFile(URL_PATH, "clip.mp4")).rejects.toThrow("Failed to fetch file (404)");
  });

  it("unzips a small batch archive and shares each entry as its own file", async () => {
    const zipped = zipSync({ "photo1.jpg": strToU8("a"), "photo2.jpg": strToU8("b") });
    stubFetch(new Blob([new Uint8Array(zipped)], { type: "application/zip" }));
    const share = mobile(true);

    expect(await saveDownloadedZipAsFiles(URL_PATH, "Carousel.zip")).toBe("shared");
    const files = share.mock.calls[0][0].files as File[];
    expect(files.map((f) => f.name).sort()).toEqual(["photo1.jpg", "photo2.jpg"]);
    expect(files[0].type).toBe("image/jpeg");
  });
});

describe("helpers", () => {
  it("shouldUseShareSheet is true for a coarse pointer or mobile UA with share support", () => {
    const file = new File(["x"], "a.mp4");
    stubPointer(true);
    vi.stubGlobal("navigator", { userAgent: DESKTOP_UA, canShare: () => true, share: vi.fn() });
    expect(shouldUseShareSheet([file])).toBe(true);
    stubPointer(false);
    vi.stubGlobal("navigator", { userAgent: "Mozilla/5.0 (Linux; Android 14)", canShare: () => true, share: vi.fn() });
    expect(shouldUseShareSheet([file])).toBe(true);
    expect(shouldUseShareSheet([])).toBe(false);
    vi.stubGlobal("navigator", { userAgent: DESKTOP_UA, canShare: () => true, share: vi.fn() });
    expect(shouldUseShareSheet([file])).toBe(false);
  });

  it("sanitizes forbidden characters but keeps Unicode titles", () => {
    expect(sanitizeFilename('안녕 세계: "a/b"?.mp4')).toBe("안녕 세계_ _a_b__.mp4");
    expect(sanitizeFilename("...")).toBe("download");
  });

  it("revokes a blob URL only after the delayed fallback download starts", async () => {
    vi.useFakeTimers();
    try {
      stubFetch(videoBlob());
      stubPointer(true);
      vi.stubGlobal("navigator", { userAgent: MOBILE_UA, canShare: () => false, share: vi.fn() });
      const revoke = stubUrl();
      clickedAnchors();
      await saveDownloadedFile(URL_PATH, "clip.mp4");
      expect(revoke).not.toHaveBeenCalled();
      vi.runAllTimers();
      expect(revoke).toHaveBeenCalledWith("blob:fake");
    } finally {
      vi.useRealTimers();
    }
  });
});
