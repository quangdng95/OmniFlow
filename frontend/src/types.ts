export type Platform = "YouTube" | "Instagram" | "TikTok" | "Facebook" | "RedNote" | "Link";

// Instagram photos resolve to "image"; everything else is "video". Optional so
// non-Instagram responses (which never set it) default to video-like behavior.
export type MediaKind = "image" | "video";

export interface VideoInfo {
  type: "video";
  title: string;
  uploader: string;
  thumbnail: string | null;
  platform: Platform;
  qualities: string[];
  duration: string | null;
  kind?: MediaKind;
}

export interface PlaylistItem {
  id: string | null;
  title: string;
  thumbnail: string | null;
  duration: string | null;
  qualities: string[];
  kind?: MediaKind;
  // 1-based playlist position for UI-only numbering (e.g. shown as "01."). Never
  // part of the physical filename (PRD §7). Absent for a 1-item list / Instagram
  // items, in which case the row's array index is used as a fallback.
  position?: number | null;
  // Channel/uploader name for the item, when the flat extraction exposes it.
  uploader?: string;
  // A YouTube playlist/channel item carries its own video URL; an Instagram
  // carousel/Story item carries a 1-based entry_index into the original URL.
  // Exactly one is set, and batch download dispatches on which.
  url?: string;
  entry_index?: number;
  // False for a hidden/removed playlist video ([Private video]/[Deleted video]/
  // no duration). Absent means available (Instagram items never set it).
  is_available?: boolean;
}

export interface PlaylistCheckResult {
  type: "playlist";
  platform: Platform;
  title: string;
  items: PlaylistItem[];
  // True when a large channel/playlist was capped, so the UI can say so.
  truncated?: boolean;
}

export type CheckResult = VideoInfo | PlaylistCheckResult;

export type CookiesStatus = "none" | "valid" | "no_session";

export interface Settings {
  path: string;
  cookies_path: string;
  cookies_status: CookiesStatus;
}

export type JobStatus = "running" | "done" | "cancelled" | "error";

export type BatchItemStatus = "pending" | "downloading" | "done" | "error";

// One video's own progress within a batch (playlist) download.
export interface BatchItemProgress {
  title: string;
  status: BatchItemStatus;
  percent: number;
}

// A playlist row's download state in the UI ("idle" = never started).
export type RowDownloadStatus = BatchItemStatus | "idle";

export interface RowProgress {
  status: RowDownloadStatus;
  percent: number;
}

export interface JobProgress {
  status: JobStatus;
  percent: number;
  text: string;
  filename: string | null;
  // Present only for batch (playlist) jobs: which item is downloading, how many
  // total, how many finished successfully, and the per-item progress list.
  item?: number | null;
  total?: number | null;
  saved_count?: number | null;
  items_progress?: BatchItemProgress[] | null;
}

// One selected item sent to /api/download-batch. Exactly one of url/entryIndex.
export interface BatchItem {
  title: string;
  url?: string;
  entryIndex?: number;
}
