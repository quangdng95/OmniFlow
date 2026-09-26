import { unzipSync } from "fflate";
import { translations } from "../i18n/translations";
import { detectLanguage } from "../i18n/storage";

const downloadBlob = (blob: Blob, filename: string): void => {
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(objectUrl);
};

// A save that's already been fetched (and, for a batch, unzipped) and only
// needs handing to the share sheet / a download link.
export interface PreparedSave {
  files: File[];
  fallbackBlob: Blob;
  fallbackFilename: string;
}

// Saving a finished download on mobile Safari via a plain <a href download>
// link hands the file to Safari's own download manager - it lands in the
// Files app's "Downloads" folder (or iCloud Drive), never the Photos app,
// and getting it into Photos from there takes several more manual taps
// (open Files > find it > Share > Save Video). The Web Share API's `files`
// support lets a page hand the file straight to the OS share sheet instead,
// which offers "Save Video"/"Save Image" (saving directly into Photos) as
// its top suggestion for image/video content - one tap, no Files app detour.
// Falls back to a plain download link wherever share-with-files isn't
// supported (desktop browsers, older WebKit, non-Apple platforms), and
// whenever `files` is empty - navigator.canShare's handling of an empty
// file list isn't consistent enough across engines to trust.
//
// navigator.share() also needs *transient user activation*: iOS Safari
// rejects it with NotAllowedError ("The request is not allowed by the user
// agent or the platform in the current context…") once the tap that
// triggered it is more than a moment old. Fetching + unzipping a multi-MB
// batch between the tap and share() routinely burns through that window
// (MISTAKES.md 2026-09-27) - so callers prepare the files *ahead* of the tap
// (preparePlainFile / prepareZipFiles) and this function calls share()
// before any await.
export async function sharePreparedSave(prepared: PreparedSave): Promise<"shared" | "downloaded"> {
  const { files, fallbackBlob, fallbackFilename } = prepared;
  if (files.length > 0 && navigator.canShare?.({ files })) {
    await navigator.share({ files });
    return "shared";
  }
  downloadBlob(fallbackBlob, fallbackFilename);
  return "downloaded";
}

export const isNotAllowedError = (error: unknown): boolean =>
  error instanceof Error && error.name === "NotAllowedError";

const fetchBlob = async (url: string): Promise<Blob> => {
  const response = await fetch(url, { credentials: "include" });
  if (!response.ok) {
    throw new Error(translations[detectLanguage()].apiErrors.fileFetchFailed.replace("{status}", String(response.status)));
  }
  return response.blob();
};

export async function preparePlainFile(url: string, filename: string): Promise<PreparedSave> {
  const blob = await fetchBlob(url);
  const file = new File([blob], filename, {
    type: blob.type || "application/octet-stream",
  });
  return { files: [file], fallbackBlob: blob, fallbackFilename: filename };
}

export async function saveDownloadedFile(
  url: string,
  filename: string
): Promise<"shared" | "downloaded"> {
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
export async function prepareZipFiles(url: string, fallbackFilename: string): Promise<PreparedSave> {
  const zipBlob = await fetchBlob(url);

  let entries: Record<string, Uint8Array>;
  try {
    entries = unzipSync(new Uint8Array(await zipBlob.arrayBuffer()));
  } catch {
    entries = {};
  }

  const files = Object.entries(entries)
    .filter(([name, data]) => !name.endsWith("/") && data.byteLength > 0)
    .map(([name, data]) => new File([new Uint8Array(data)], name, { type: mimeTypeFor(name) }));

  return { files, fallbackBlob: zipBlob, fallbackFilename };
}

export async function saveDownloadedZipAsFiles(
  url: string,
  fallbackFilename: string
): Promise<"shared" | "downloaded"> {
  return sharePreparedSave(await prepareZipFiles(url, fallbackFilename));
}
