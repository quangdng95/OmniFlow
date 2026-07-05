export type Platform = "YouTube" | "Instagram" | "TikTok" | "Facebook" | "RedNote" | "Link";

export interface VideoInfo {
  title: string;
  uploader: string;
  thumbnail: string | null;
  platform: Platform;
  qualities: string[];
  duration: string | null;
}

export type CookiesStatus = "none" | "valid" | "no_session";

export interface Settings {
  path: string;
  cookies_path: string;
  cookies_status: CookiesStatus;
}

export type JobStatus = "running" | "done" | "cancelled" | "error";

export interface JobProgress {
  status: JobStatus;
  percent: number;
  text: string;
  filename: string | null;
}
