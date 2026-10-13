import { afterEach, describe, expect, it, vi } from "vitest";
import { zipSync, strToU8 } from "fflate";
import { sanitizeFilename, saveDownloadedFile, saveDownloadedZipAsFiles, shouldUseShareSheet } from "./saveFile";

const MOBILE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)";
const DESKTOP_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/130";

const stubPointer = (coarse: boolean): void => {
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: coarse && query.includes("coarse") }));
};

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("saveDownloadedFile", () => {
  it("throws a friendly error when the fetch itself fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 404 }));

    await expect(saveDownloadedFile("/api/download-file/job1", "clip.mp4")).rejects.toThrow(
      "Failed to fetch file (404)"
    );
  });

  it("shares the file via the OS share sheet when share-with-files is supported", async () => {
    const blob = new Blob(["fake bytes"], { type: "video/mp4" });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, blob: () => Promise.resolve(blob) }));
    const share = vi.fn().mockResolvedValue(undefined);
    stubPointer(true);
    vi.stubGlobal("navigator", { userAgent: MOBILE_UA, canShare: () => true, share });

    const result = await saveDownloadedFile("/api/download-file/job1", "clip.mp4");

    expect(result).toBe("shared");
    expect(share).toHaveBeenCalledTimes(1);
    const sharedFiles = share.mock.calls[0][0].files;
    expect(sharedFiles).toHaveLength(1);
    expect(sharedFiles[0].name).toBe("clip.mp4");
  });

  it("falls back to a plain download link when share-with-files isn't supported", async () => {
    const blob = new Blob(["fake bytes"], { type: "video/mp4" });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, blob: () => Promise.resolve(blob) }));
    vi.stubGlobal("navigator", {});
    vi.stubGlobal("URL", { createObjectURL: vi.fn().mockReturnValue("blob:fake"), revokeObjectURL: vi.fn() });
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    const result = await saveDownloadedFile("/api/download-file/job1", "clip.mp4");

    expect(result).toBe("downloaded");
    expect(clickSpy).toHaveBeenCalledTimes(1);
  });
});

describe("desktop vs mobile", () => {
  const okFetch = () =>
    vi.fn().mockResolvedValue({ ok: true, blob: () => Promise.resolve(new Blob(["x"], { type: "video/mp4" })) });

  it("never opens the share sheet on a desktop (fine pointer) even when the API exists", async () => {
    vi.stubGlobal("fetch", okFetch());
    stubPointer(false);
    const share = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { userAgent: DESKTOP_UA, canShare: () => true, share });
    vi.stubGlobal("URL", { createObjectURL: vi.fn().mockReturnValue("blob:fake"), revokeObjectURL: vi.fn() });
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    const result = await saveDownloadedFile("/api/download-file/job1", "클립.mp4");

    expect(result).toBe("downloaded");
    expect(share).not.toHaveBeenCalled();
    expect(clickSpy).toHaveBeenCalledTimes(1);
  });

  it("falls back to an anchor download on mobile when canShare says no", async () => {
    vi.stubGlobal("fetch", okFetch());
    stubPointer(true);
    const share = vi.fn();
    vi.stubGlobal("navigator", { userAgent: MOBILE_UA, canShare: () => false, share });
    vi.stubGlobal("URL", { createObjectURL: vi.fn().mockReturnValue("blob:fake"), revokeObjectURL: vi.fn() });
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    expect(await saveDownloadedFile("/api/download-file/job1", "clip.mp4")).toBe("downloaded");
    expect(share).not.toHaveBeenCalled();
    expect(clickSpy).toHaveBeenCalledTimes(1);
  });

  it("shouldUseShareSheet is true for a coarse pointer or mobile UA with share support", () => {
    const file = new File(["x"], "a.mp4");
    stubPointer(true);
    vi.stubGlobal("navigator", { userAgent: DESKTOP_UA, canShare: () => true, share: vi.fn() });
    expect(shouldUseShareSheet([file])).toBe(true);
    stubPointer(false);
    vi.stubGlobal("navigator", { userAgent: "Mozilla/5.0 (Linux; Android 14)", canShare: () => true, share: vi.fn() });
    expect(shouldUseShareSheet([file])).toBe(true);
    expect(shouldUseShareSheet([])).toBe(false);
  });

  it("sanitizes forbidden characters but keeps Unicode titles", () => {
    expect(sanitizeFilename('안녕 세계: "a/b"?.mp4')).toBe("안녕 세계_ _a_b__.mp4");
    expect(sanitizeFilename("...")).toBe("download");
  });

  it("revokes the object URL after the download starts", async () => {
    vi.useFakeTimers();
    try {
      vi.stubGlobal("fetch", okFetch());
      stubPointer(false);
      vi.stubGlobal("navigator", { userAgent: DESKTOP_UA });
      const revoke = vi.fn();
      vi.stubGlobal("URL", { createObjectURL: vi.fn().mockReturnValue("blob:fake"), revokeObjectURL: revoke });
      vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
      await saveDownloadedFile("/api/download-file/job1", "clip.mp4");
      expect(revoke).not.toHaveBeenCalled();
      vi.runAllTimers();
      expect(revoke).toHaveBeenCalledWith("blob:fake");
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("saveDownloadedZipAsFiles", () => {
  const buildZipResponse = (entries: Record<string, string>) => {
    const zipped = zipSync(
      Object.fromEntries(Object.entries(entries).map(([name, content]) => [name, strToU8(content)]))
    );
    const blob = new Blob([new Uint8Array(zipped)], { type: "application/zip" });
    return { ok: true, blob: () => Promise.resolve(blob) };
  };

  it("unzips the batch archive and shares each entry as its own file", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(buildZipResponse({ "photo1.jpg": "a", "photo2.jpg": "b" }))
    );
    const share = vi.fn().mockResolvedValue(undefined);
    stubPointer(true);
    vi.stubGlobal("navigator", { userAgent: MOBILE_UA, canShare: () => true, share });

    const result = await saveDownloadedZipAsFiles("/api/download-file/job1", "Carousel.zip");

    expect(result).toBe("shared");
    const sharedFiles = share.mock.calls[0][0].files as File[];
    expect(sharedFiles.map((f) => f.name).sort()).toEqual(["photo1.jpg", "photo2.jpg"]);
    expect(sharedFiles[0].type).toBe("image/jpeg");
  });

  it("falls back to downloading the raw zip when share-with-files isn't supported", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(buildZipResponse({ "photo1.jpg": "a" })));
    vi.stubGlobal("navigator", {});
    vi.stubGlobal("URL", { createObjectURL: vi.fn().mockReturnValue("blob:fake"), revokeObjectURL: vi.fn() });
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    const result = await saveDownloadedZipAsFiles("/api/download-file/job1", "Carousel.zip");

    expect(result).toBe("downloaded");
    expect(clickSpy).toHaveBeenCalledTimes(1);
  });

  it("falls back to downloading the raw zip when the archive has no real entries", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(buildZipResponse({})));
    vi.stubGlobal("navigator", { canShare: () => true, share: vi.fn() });
    vi.stubGlobal("URL", { createObjectURL: vi.fn().mockReturnValue("blob:fake"), revokeObjectURL: vi.fn() });
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    const result = await saveDownloadedZipAsFiles("/api/download-file/job1", "Carousel.zip");

    expect(result).toBe("downloaded");
    expect(clickSpy).toHaveBeenCalledTimes(1);
  });
});
