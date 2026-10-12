import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import HomePage from "./HomePage";
import { api } from "../api";
import { LanguageProvider } from "../i18n/LanguageContext";
import type { PlaylistCheckResult, VideoInfo } from "../types";

vi.mock("../api", () => ({
  api: {
    checkLink: vi.fn(),
    startDownload: vi.fn(),
    startBatchDownload: vi.fn(),
    getProgress: vi.fn(),
    cancelJob: vi.fn(),
    openFolder: vi.fn(),
    getClipboard: vi.fn(),
  },
}));
const mockedApi = vi.mocked(api, true);

// The labels exactly as the API returns them: lowercase. The UI shows them in
// capitals through CSS only (text-transform), and the backend does NOT
// normalise case - an uppercase "2160P" silently falls back to "Best".
const LABELS = ["2160p", "1440p", "1080p", "720p", "480p", "360p", "Best", "Audio Only"];

const VIDEO: VideoInfo = {
  type: "video", title: "Video A", uploader: "U", thumbnail: null, platform: "YouTube",
  qualities: LABELS, duration: "01:00",
};
const PLAYLIST: PlaylistCheckResult = {
  type: "playlist", platform: "YouTube", title: "My Playlist",
  items: [1, 2].map((n) => ({
    id: `i${n}`, title: `Item ${n}`, position: n, thumbnail: null, duration: "1:00",
    url: `https://youtu.be/${n}`, qualities: LABELS, is_available: true,
  })),
};

const renderHome = () =>
  render(
    <LanguageProvider>
      <HomePage onNavigate={vi.fn()} />
    </LanguageProvider>
  );

describe("quality label sent to the API", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedApi.startDownload.mockResolvedValue({ job_id: "j" });
    mockedApi.startBatchDownload.mockResolvedValue({ job_id: "b" });
    mockedApi.getProgress.mockResolvedValue({ status: "running", percent: 1, text: "", filename: null });
  });

  it.each(LABELS)("single video: picking %s sends that exact label", async (label) => {
    mockedApi.checkLink.mockResolvedValue(VIDEO);
    const user = userEvent.setup({ delay: null });
    renderHome();
    await user.type(screen.getByPlaceholderText("Copy and Paste your url"), "https://youtube.com/watch?v=q");
    await screen.findByText("Video A", undefined, { timeout: 3000 });
    await user.click(screen.getByRole("tab", { name: label }));
    await user.click(screen.getByRole("button", { name: /start download/i }));
    await waitFor(() => expect(mockedApi.startDownload).toHaveBeenCalledTimes(1));
    expect(mockedApi.startDownload.mock.calls[0][2]).toBe(label);
  });

  it.each(["2160p", "1440p", "Audio Only"])("playlist: Download All with %s sends that exact label", async (label) => {
    mockedApi.checkLink.mockResolvedValue(PLAYLIST);
    const user = userEvent.setup({ delay: null });
    renderHome();
    await user.type(screen.getByPlaceholderText("Copy and Paste your url"), "https://youtube.com/playlist?list=PLq");
    await screen.findByText("Item 1", undefined, { timeout: 3000 });
    await user.click(screen.getByRole("tab", { name: label }));
    await user.click(screen.getByRole("button", { name: /download all/i }));
    await waitFor(() => expect(mockedApi.startBatchDownload).toHaveBeenCalledTimes(1));
    expect(mockedApi.startBatchDownload.mock.calls[0][1]).toBe(label);
  });
});
