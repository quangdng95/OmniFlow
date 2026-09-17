import { afterEach, describe, expect, it, vi } from "vitest";
import { zipSync, strToU8 } from "fflate";
import { saveDownloadedFile, saveDownloadedZipAsFiles } from "./saveFile";

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
    vi.stubGlobal("navigator", { canShare: () => true, share });

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
    vi.stubGlobal("navigator", { canShare: () => true, share });

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
