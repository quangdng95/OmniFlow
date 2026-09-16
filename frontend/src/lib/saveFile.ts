// Saving a finished download on mobile Safari via a plain <a href download>
// link hands the file to Safari's own download manager - it lands in the
// Files app's "Downloads" folder (or iCloud Drive), never the Photos app,
// and getting it into Photos from there takes several more manual taps
// (open Files > find it > Share > Save Video). The Web Share API's `files`
// support lets a page hand the file straight to the OS share sheet instead,
// which offers "Save Video"/"Save Image" (saving directly into Photos) as
// its top suggestion for image/video content - one tap, no Files app detour.
// Falls back to the old direct-link behavior wherever share-with-files isn't
// supported (desktop browsers, older WebKit, non-Apple platforms).
export async function saveDownloadedFile(
  url: string,
  filename: string
): Promise<"shared" | "downloaded"> {
  const response = await fetch(url, { credentials: "include" });
  if (!response.ok) {
    throw new Error(`Failed to fetch file (${response.status})`);
  }
  const blob = await response.blob();
  const file = new File([blob], filename, {
    type: blob.type || "application/octet-stream",
  });

  if (navigator.canShare?.({ files: [file] })) {
    await navigator.share({ files: [file] });
    return "shared";
  }

  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(objectUrl);
  return "downloaded";
}
