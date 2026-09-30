import type { Platform } from "../types";

export const HISTORY_STORAGE_KEY = "omniflow-history";
export const HISTORY_LIMIT = 10;

export interface HistoryEntry {
  url: string;
  title: string;
  platform: Platform;
  thumbnail: string | null;
  downloadedAt: number;
}

const isEntry = (value: unknown): value is HistoryEntry => {
  if (typeof value !== "object" || value === null) return false;
  const entry = value as Record<string, unknown>;
  return (
    typeof entry.url === "string" &&
    entry.url.length > 0 &&
    typeof entry.title === "string" &&
    typeof entry.platform === "string" &&
    (entry.thumbnail === null || typeof entry.thumbnail === "string") &&
    typeof entry.downloadedAt === "number"
  );
};

// Stored per browser (localStorage), never sent to the server: "history" here
// means "what this device downloaded", and on the shared cloud deployment a
// server-side list would mix every visitor's links together. Every access is
// wrapped because localStorage can throw (private mode, blocked site data).
export const loadHistory = (): HistoryEntry[] => {
  try {
    const raw = localStorage.getItem(HISTORY_STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(isEntry).slice(0, HISTORY_LIMIT);
  } catch {
    return [];
  }
};

const saveHistory = (entries: HistoryEntry[]): void => {
  try {
    localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(entries));
  } catch {
    // Best-effort: a full/blocked store just means this download isn't listed.
  }
};

// Newest first, one row per URL (downloading the same link again moves it to
// the top instead of listing it twice), capped at HISTORY_LIMIT.
export const recordDownload = (entry: Omit<HistoryEntry, "downloadedAt">): HistoryEntry[] => {
  const url = entry.url.trim();
  if (!url) return loadHistory();
  const next = [
    { ...entry, url, downloadedAt: Date.now() },
    ...loadHistory().filter((existing) => existing.url !== url),
  ].slice(0, HISTORY_LIMIT);
  saveHistory(next);
  return next;
};

export const removeHistoryEntry = (url: string): HistoryEntry[] => {
  const next = loadHistory().filter((entry) => entry.url !== url);
  saveHistory(next);
  return next;
};

export const clearHistory = (): void => {
  try {
    localStorage.removeItem(HISTORY_STORAGE_KEY);
  } catch {
    // Nothing stored that we could remove.
  }
};
