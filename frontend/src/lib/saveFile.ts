import { unzipSync } from "fflate";
import { translations } from "../i18n/translations";
import { detectLanguage } from "../i18n/storage";

// Characters Windows/macOS/Linux filesystems or browsers reject in a file
// name. Unicode letters (Korean, Vietnamese, ...) are kept as they are.
// eslint-disable-next-line no-control-regex
const FORBIDDEN_FILENAME_CHARS = /[\\/:*?"<>|\u0000-\u001f]/g;

export const sanitizeFilename = (filename: string): string => {
  const cleaned = filename.replace(FORBIDDEN_FILENAME_CHARS, "_").replace(/^[\s.]+|[\s.]+$/g, "");
  return cleaned || "download";
};

// Revoking in the same tick as click() can cancel the download in some
// browsers, so give it a moment to start first.
const REVOKE_DELAY_MS = 10_000;

const downloadBlob = (blob: Blob, filename: string): void => {
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = sanitizeFilename(filename);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  setTimeout(() => URL.revokeObjectURL(objectUrl), REVOKE_DELAY_MS);
};

// Where the user is, as far as saving a file goes. Each platform has a different right answer:
//  ios      - the share sheet (navigator.share with a File), which offers "Save Video" / "Save Image"
//             straight into Photos. A plain download link only lands in the Files app.
//  android  - a plain download link: Chrome saves it to Downloads and video shows up in the gallery.
//  desktop  - a plain download link, streamed to disk by the browser (nothing is held in RAM).
// iPadOS 13+ Safari reports a Mac user agent ("MacIntel"), told apart by its touch screen.
export type SavePlatform = "ios" | "android" | "desktop";

export const getSavePlatform = (): SavePlatform => {
  if (typeof navigator === "undefined") return "desktop";
  const ua = navigator.userAgent ?? "";
  if (/iPhone|iPad|iPod/i.test(ua)) return "ios";
  if (navigator.platform === "MacIntel" && (navigator.maxTouchPoints ?? 0) > 1) return "ios";
  if (/Android/i.test(ua)) return "android";
  return "desktop";
};

// On iOS the file is fetched into memory ahead of the tap, so the tap can call share() at once. Above
// this size that is not worth the memory (Safari kills a tab that holds too much), so the file is
// downloaded straight to the Files app instead.
export const IOS_PREPARE_MAX_BYTES = 400 * 1024 * 1024;

// Safety net so a stuck connection can never leave the button on "Preparing...".
const PREPARE_TIMEOUT_MS = 10 * 60_000;

export type DirectReason = "not-ios" | "too-big" | "cannot-share" | "no-memory";

const canShareFiles = (files: File[]): boolean =>
  files.length > 0 && typeof navigator !== "undefined" && typeof navigator.share === "function" && !!navigator.canShare?.({ files });

// Lets the browser stream the file to disk itself. Same-origin, so the trust
// cookie rides along; no token ever goes into the URL.
const directDownload = (url: string, filename: string): void => {
  const link = document.createElement("a");
  link.href = url;
  link.download = sanitizeFilename(filename);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
};

// A save that's been prepared ahead of the tap: either files ready for the share sheet (iOS) or a URL
// the browser streams to disk (everything else, and iOS when the file is too big / cannot be shared).
export interface PreparedSave {
  files: File[];
  fallbackBlob?: Blob;
  fallbackFilename: string;
  directUrl?: string;
  // Why there is no share sheet for this save (only set together with directUrl).
  reason?: DirectReason;
}

// iOS: navigator.share() needs *transient user activation* - Safari rejects it with NotAllowedError
// once the tap is more than a moment old - so callers prepare the files ahead of the tap
// (preparePlainFile / prepareZipFiles) and this function calls share() before any await. Do not put
// an await in front of the share() call (docs/internal/MISTAKES.md 2026-09-27).
export async function sharePreparedSave(prepared: PreparedSave): Promise<"shared" | "downloaded"> {
  const { files, fallbackBlob, fallbackFilename, directUrl } = prepared;
  if (directUrl) {
    directDownload(directUrl, fallbackFilename);
    return "downloaded";
  }
  if (getSavePlatform() === "ios" && canShareFiles(files)) {
    await navigator.share({ files });
    return "shared";
  }
  if (fallbackBlob) downloadBlob(fallbackBlob, fallbackFilename);
  return "downloaded";
}

export const isNotAllowedError = (error: unknown): boolean =>
  error instanceof Error && error.name === "NotAllowedError";

// The server answered the file request with an error status (shown to the user as is).
class FileFetchError extends Error {}

export const isAbortError = (error: unknown): boolean =>
  error instanceof Error && error.name === "AbortError";

export interface PrepareOptions {
  // 0-100 while the file is being fetched; not called when the size is unknown.
  onProgress?: (percent: number) => void;
  // Aborts the fetch (new video selected, component unmounted) and frees what was read so far.
  signal?: AbortSignal;
}

// Fetches the finished file with progress. Returns null when it is larger than `maxBytes` (nothing is
// kept) so the caller can stream it to disk instead.
const fetchBlobWithProgress = async (url: string, maxBytes: number, options: PrepareOptions): Promise<Blob | null> => {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), PREPARE_TIMEOUT_MS);
  const onOuterAbort = () => controller.abort();
  options.signal?.addEventListener("abort", onOuterAbort);
  if (options.signal?.aborted) controller.abort();
  try {
    const response = await fetch(url, { credentials: "include", signal: controller.signal });
    if (!response.ok) {
      throw new FileFetchError(translations[detectLanguage()].apiErrors.fileFetchFailed.replace("{status}", String(response.status)));
    }
    const total = Number(response.headers?.get("Content-Length"));
    const known = Number.isFinite(total) && total > 0;
    if (known && total > maxBytes) {
      controller.abort();
      return null;
    }
    const reader = response.body?.getReader?.();
    if (!reader) {
      const blob = await response.blob();
      options.onProgress?.(100);
      return blob.size > maxBytes ? null : blob;
    }
    const chunks: Uint8Array[] = [];
    let received = 0;
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      chunks.push(value);
      received += value.byteLength;
      if (received > maxBytes) {
        await reader.cancel();
        return null;
      }
      if (known) options.onProgress?.(Math.min(99, Math.floor((received / total) * 100)));
    }
    options.onProgress?.(100);
    return new Blob(chunks as BlobPart[], { type: response.headers?.get("Content-Type") ?? "" });
  } finally {
    clearTimeout(timer);
    options.signal?.removeEventListener("abort", onOuterAbort);
  }
};

const directSave = (url: string, filename: string, reason: DirectReason): PreparedSave => ({
  files: [],
  fallbackFilename: filename,
  directUrl: url,
  reason,
});

// Fetching can fail because the page ran out of memory (a RangeError / a TypeError from a dead stream):
// that is not the user's problem, the file is simply streamed to disk instead. A real HTTP error or an
// abort still surfaces.
const shouldFallBackToDirect = (error: unknown): boolean => !isAbortError(error) && !(error instanceof FileFetchError);

export async function preparePlainFile(url: string, filename: string, options: PrepareOptions = {}): Promise<PreparedSave> {
  if (getSavePlatform() !== "ios") return directSave(url, filename, "not-ios");
  let blob: Blob | null;
  try {
    blob = await fetchBlobWithProgress(url, IOS_PREPARE_MAX_BYTES, options);
  } catch (error: unknown) {
    if (shouldFallBackToDirect(error)) return directSave(url, filename, "no-memory");
    throw error;
  }
  if (!blob) return directSave(url, filename, "too-big");
  const file = new File([blob], sanitizeFilename(filename), { type: blob.type || mimeTypeFor(filename) });
  if (!canShareFiles([file])) return directSave(url, filename, "cannot-share");
  return { files: [file], fallbackBlob: blob, fallbackFilename: filename };
}

export async function saveDownloadedFile(url: string, filename: string): Promise<"shared" | "downloaded"> {
  return sharePreparedSave(await preparePlainFile(url, filename));
}

const MIME_BY_EXTENSION: Record<string, string> = {
  jpg: "image/jpeg",
  jpeg: "image/jpeg",
  png: "image/png",
  webp: "image/webp",
  gif: "image/gif",
  heic: "image/heic",
  mp4: "video/mp4",
  mkv: "video/x-matroska",
  webm: "video/webm",
  m4a: "audio/mp4",
  mov: "video/quicktime",
  mp3: "audio/mpeg",
};

const mimeTypeFor = (filename: string): string => {
  const ext = filename.split(".").pop()?.toLowerCase() ?? "";
  return MIME_BY_EXTENSION[ext] ?? "application/octet-stream";
};

// A batch/playlist download arrives as one .zip (backend groups every item
// into a single archive so the transfer stays one HTTP request). Sharing
// that .zip via the OS share sheet only ever offers "Save to Files" - a zip
// isn't a photo. Unzipping it here in the browser and handing the real
// image/video files to the share sheet together lets iOS recognize them and
// offer "Save N Images" straight into Photos instead, matching what saving
// a single item already does. Falls back to downloading the original .zip
// wherever share-with-files isn't supported, or if the zip turns out to be
// empty/corrupt.
export async function prepareZipFiles(url: string, fallbackFilename: string, options: PrepareOptions = {}): Promise<PreparedSave> {
  if (getSavePlatform() !== "ios") return directSave(url, fallbackFilename, "not-ios");
  let zipBlob: Blob | null;
  try {
    zipBlob = await fetchBlobWithProgress(url, IOS_PREPARE_MAX_BYTES, options);
  } catch (error: unknown) {
    if (shouldFallBackToDirect(error)) return directSave(url, fallbackFilename, "no-memory");
    throw error;
  }
  if (!zipBlob) return directSave(url, fallbackFilename, "too-big");

  let entries: Record<string, Uint8Array>;
  try {
    entries = unzipSync(new Uint8Array(await zipBlob.arrayBuffer()));
  } catch {
    entries = {};
  }

  const files = Object.entries(entries)
    .filter(([name, data]) => !name.endsWith("/") && data.byteLength > 0)
    .map(([name, data]) => new File([new Uint8Array(data)], name, { type: mimeTypeFor(name) }));

  if (files.length > 0 && !canShareFiles(files)) return directSave(url, fallbackFilename, "cannot-share");
  return { files, fallbackBlob: zipBlob, fallbackFilename };
}

export async function saveDownloadedZipAsFiles(
  url: string,
  fallbackFilename: string
): Promise<"shared" | "downloaded"> {
  return sharePreparedSave(await prepareZipFiles(url, fallbackFilename));
}
