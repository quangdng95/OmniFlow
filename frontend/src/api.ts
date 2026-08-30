import type { BatchItem, CheckResult, CookiesStatus, JobProgress, Settings } from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    throw new Error("Can't reach the OmniFlow server. Make sure it's running, then reload this page.");
  }
  let data;
  try {
    data = await res.json();
  } catch {
    // A route that doesn't exist on the server currently answering this
    // request (e.g. a local-only endpoint like /api/clipboard called
    // against a remote_web deployment, which never registers it) returns a
    // plain HTML 404 page, not JSON - never let that leak as a raw
    // "Unexpected token '<'" JSON.parse error.
    throw new Error(`Request failed${res.ok ? "" : ` (${res.status})`}.`);
  }
  if (!res.ok) {
    throw new Error(data.error || "Request failed");
  }
  return data as T;
}

export const api = {
  getSettings: () => request<Settings>("/api/settings"),

  updateSettings: (patch: Partial<Settings>) =>
    request<Settings>("/api/settings", { method: "POST", body: JSON.stringify(patch) }),

  browseFolder: () => request<{ path: string }>("/api/browse", { method: "POST" }),

  browseFile: () =>
    request<{ path: string; cookies_status: CookiesStatus }>("/api/browse-file", { method: "POST" }),

  checkLink: (url: string) =>
    request<CheckResult>("/api/check", { method: "POST", body: JSON.stringify({ url }) }),

  startDownload: (url: string, title: string, quality: string, entryIndex?: number) =>
    request<{ job_id: string }>("/api/download", {
      method: "POST",
      body: JSON.stringify({ url, title, quality, entry_index: entryIndex }),
    }),

  // Batch-download several selected playlist/carousel items in one job.
  startBatchDownload: (url: string, quality: string, items: BatchItem[]) =>
    request<{ job_id: string }>("/api/download-batch", {
      method: "POST",
      body: JSON.stringify({
        url,
        quality,
        items: items.map((it) => ({ title: it.title, url: it.url, entry_index: it.entryIndex })),
      }),
    }),

  getProgress: (jobId: string) => request<JobProgress>(`/api/progress/${jobId}`),

  cancelJob: (jobId: string) => request<{ ok: true }>(`/api/cancel/${jobId}`, { method: "POST" }),

  openFolder: () => request<{ ok: true }>("/api/open-folder", { method: "POST" }),

  openLogs: () => request<{ ok: true; has_logs: boolean }>("/api/open-logs", { method: "POST" }),

  resetSettings: () => request<Settings>("/api/reset-settings", { method: "POST" }),

  getClipboard: () => request<{ text: string }>("/api/clipboard"),
};
