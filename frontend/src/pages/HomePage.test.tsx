import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import HomePage from "./HomePage";
import { api } from "../api";
import { LanguageProvider } from "../i18n/LanguageContext";
import type { Page } from "../components/Header";
import type { JobProgress, PlaylistCheckResult, VideoInfo } from "../types";

const renderHomePage = (onNavigate: (page: Page) => void = vi.fn()) =>
  render(
    <LanguageProvider>
      <HomePage onNavigate={onNavigate} />
    </LanguageProvider>
  );

vi.mock("../api", () => ({
  api: {
    getSettings: vi.fn(),
    updateSettings: vi.fn(),
    browseFolder: vi.fn(),
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

const VIDEO_A: VideoInfo = {
  type: "video",
  title: "Video A",
  uploader: "Uploader A",
  thumbnail: null,
  platform: "YouTube",
  qualities: ["720p", "360p", "Best", "Audio Only"],
  duration: "01:00",
};

const VIDEO_B: VideoInfo = {
  type: "video",
  title: "Video B",
  uploader: "Uploader B",
  thumbnail: null,
  platform: "TikTok",
  qualities: ["1080p", "Best", "Audio Only"],
  duration: "00:30",
};

const RUNNING_PROGRESS: JobProgress = {
  status: "running",
  percent: 10,
  text: "Downloading... (10%)",
  filename: null,
};

const PLAYLIST_RESULT: PlaylistCheckResult = {
  type: "playlist",
  platform: "Instagram",
  title: "Story by someone",
  items: [
    { id: "item1", title: "Story item 1", thumbnail: null, duration: "00:15", entry_index: 1, qualities: ["720p", "Best", "Audio Only"] },
    { id: "item2", title: "Story item 2", thumbnail: null, duration: "00:08", entry_index: 2, qualities: ["Best", "Audio Only"] },
  ],
};

const YT_PLAYLIST: PlaylistCheckResult = {
  type: "playlist",
  platform: "YouTube",
  title: "My Playlist",
  truncated: false,
  items: [
    { id: "v1", title: "Playlist Video 1", thumbnail: null, duration: "03:00", url: "https://youtube.com/watch?v=v1", qualities: ["Best", "1080p", "720p", "480p", "Audio Only"] },
    { id: "v2", title: "Playlist Video 2", thumbnail: null, duration: "04:00", url: "https://youtube.com/watch?v=v2", qualities: ["Best", "1080p", "720p", "480p", "Audio Only"] },
  ],
};

const PL_Q = ["Best", "1080p", "720p", "480p", "Audio Only"];

const YT_PLAYLIST_SINGLE: PlaylistCheckResult = {
  type: "playlist",
  platform: "YouTube",
  title: "One video",
  items: [
    { id: "s", title: "Solo Video", thumbnail: null, duration: "02:00", url: "https://youtube.com/watch?v=solo", qualities: PL_Q, is_available: true },
  ],
};

const YT_PLAYLIST_WITH_DEAD: PlaylistCheckResult = {
  type: "playlist",
  platform: "YouTube",
  title: "Mixed Playlist",
  items: [
    { id: "a", title: "Good One", position: 1, thumbnail: null, duration: "03:00", url: "u1", qualities: PL_Q, is_available: true },
    { id: "b", title: "[Private video]", position: 2, thumbnail: null, duration: null, url: "u2", qualities: PL_Q, is_available: false },
    { id: "c", title: "Good Two", position: 3, thumbnail: null, duration: "04:00", url: "u3", qualities: PL_Q, is_available: true },
  ],
};

const IG_PHOTO: VideoInfo = {
  type: "video",
  title: "A nice photo",
  uploader: "",
  thumbnail: null,
  platform: "Instagram",
  qualities: ["Image"],
  duration: null,
  kind: "image",
};

const IG_CAROUSEL: PlaylistCheckResult = {
  type: "playlist",
  platform: "Instagram",
  title: "An album",
  items: [
    { id: "1", title: "Slide 1", thumbnail: null, duration: null, entry_index: 1, qualities: ["Image"], kind: "image" },
    { id: "2", title: "Slide 2", thumbnail: null, duration: null, entry_index: 2, qualities: ["Video"], kind: "video" },
  ],
};

// Real shape captured live from /api/check for the owner's reported "broken"
// YouTube Mix URL (watch?v=dwWOEA00K8s&list=RDKzl6cT_u7RA&index=6) - trimmed
// to 10 of the actual 50 items, keeping the real unicode titles/uploaders/
// thumbnail URLs/position numbering, to catch anything a small synthetic
// mock (YT_PLAYLIST above) wouldn't.
const REAL_YOUTUBE_MIX: PlaylistCheckResult = {
  type: "playlist",
  platform: "YouTube",
  title: "Mix - LIVE | Đến Sau - Ưng Hoàng Phúc | iTV HD - VTC13",
  truncated: false,
  items: [
    { id: "dwWOEA00K8s", title: "Xa Muôn Trùng Mây | Khánh Phương | Official Music Video", uploader: "POPS MUSIC", thumbnail: "https://i.ytimg.com/vi/dwWOEA00K8s/hqdefault.jpg", duration: "05:28", position: 1, url: "https://www.youtube.com/watch?v=dwWOEA00K8s", qualities: ["Best", "1080p", "720p", "480p", "Audio Only"], is_available: true },
    { id: "Kzl6cT_u7RA", title: "LIVE | Đến Sau - Ưng Hoàng Phúc | iTV HD - VTC13", uploader: "Ưng Hoàng Phúc", thumbnail: "https://i.ytimg.com/vi/Kzl6cT_u7RA/hqdefault.jpg", duration: "03:26", position: 2, url: "https://www.youtube.com/watch?v=Kzl6cT_u7RA", qualities: ["Best", "1080p", "720p", "480p", "Audio Only"], is_available: true },
    { id: "E3Hv3xk3di0", title: "Hình Bóng Của Mây - Khánh Phương ft. Quỳnh Nga (MV OFFICIAL)", uploader: "Khánh Phương Tube", thumbnail: "https://i.ytimg.com/vi/E3Hv3xk3di0/hqdefault.jpg", duration: "06:17", position: 3, url: "https://www.youtube.com/watch?v=E3Hv3xk3di0", qualities: ["Best", "1080p", "720p", "480p", "Audio Only"], is_available: true },
    { id: "Q8kohtX2PC4", title: "Tìm Lại Bầu Trời - Tuấn Hưng", uploader: "Tuấn Hưng", thumbnail: "https://i.ytimg.com/vi/Q8kohtX2PC4/hqdefault.jpg", duration: "05:29", position: 4, url: "https://www.youtube.com/watch?v=Q8kohtX2PC4", qualities: ["Best", "1080p", "720p", "480p", "Audio Only"], is_available: true },
    { id: "tX7G0JYCIXs", title: "Ngụ - Quang Hà - DVD Tình", uploader: "Ly Minh Nhut (AnnaHouse Studio)", thumbnail: "https://i.ytimg.com/vi/tX7G0JYCIXs/hqdefault.jpg", duration: "06:05", position: 5, url: "https://www.youtube.com/watch?v=tX7G0JYCIXs", qualities: ["Best", "1080p", "720p", "480p", "Audio Only"], is_available: true },
    { id: "qS3l_KFNGKk", title: "Hãy Xem Là Giấc Mơ - Chu Bin ( MV OFFICIAL )", uploader: "Chu Bin Official", thumbnail: "https://i.ytimg.com/vi/qS3l_KFNGKk/hqdefault.jpg", duration: "04:45", position: 6, url: "https://www.youtube.com/watch?v=qS3l_KFNGKk", qualities: ["Best", "1080p", "720p", "480p", "Audio Only"], is_available: true },
    { id: "uXMHI8z0WVc", title: "Đành Thôi Quên Lãng - Khánh Phương (MV OFFICIAL)", uploader: "Khánh Phương Tube", thumbnail: "https://i.ytimg.com/vi/uXMHI8z0WVc/hqdefault.jpg", duration: "04:50", position: 7, url: "https://www.youtube.com/watch?v=uXMHI8z0WVc", qualities: ["Best", "1080p", "720p", "480p", "Audio Only"], is_available: true },
    { id: "SItFPrgEITM", title: "Ngắm Hoa Lệ Rơi - Châu Khải Phong | Official Lyric Video", uploader: "Châu Khải Phong", thumbnail: "https://i.ytimg.com/vi/SItFPrgEITM/hqdefault.jpg", duration: "05:08", position: 8, url: "https://www.youtube.com/watch?v=SItFPrgEITM", qualities: ["Best", "1080p", "720p", "480p", "Audio Only"], is_available: true },
    { id: "v2luYYn_aAQ", title: "Cầu Vòng Khuyết - Tuấn Hưng", uploader: "Tuấn Hưng", thumbnail: "https://i.ytimg.com/vi/v2luYYn_aAQ/hqdefault.jpg", duration: "04:12", position: 9, url: "https://www.youtube.com/watch?v=v2luYYn_aAQ", qualities: ["Best", "1080p", "720p", "480p", "Audio Only"], is_available: true },
    { id: "PJalJefYFHo", title: "Yêu Cô Bạn Thân - Bằng Cường [Official MV HD]", uploader: "Bằng Cường Official", thumbnail: "https://i.ytimg.com/vi/PJalJefYFHo/hqdefault.jpg", duration: "03:58", position: 10, url: "https://www.youtube.com/watch?v=PJalJefYFHo", qualities: ["Best", "1080p", "720p", "480p", "Audio Only"], is_available: true },
  ],
};

const BATCH_RUNNING: JobProgress = {
  status: "running",
  percent: 20,
  text: "Downloading item 1 of 2...",
  filename: null,
  item: 1,
  total: 2,
  saved_count: 0,
};

describe("HomePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedApi.cancelJob.mockResolvedValue({ ok: true });
  });

  it("checks a pasted URL and defaults the quality to the first option returned", async () => {
    mockedApi.checkLink.mockResolvedValue(VIDEO_A);
    const user = userEvent.setup({ delay: null });
    renderHomePage();

    const input = screen.getByPlaceholderText("Copy and Paste your url");
    await user.type(input, "https://youtube.com/watch?v=abc");

    await waitFor(() => expect(mockedApi.checkLink).toHaveBeenCalledWith("https://youtube.com/watch?v=abc"), {
      timeout: 2000,
    });
    await screen.findByText("Video A", undefined, { timeout: 3000 });
    expect(screen.getByText("720p")).toBeInTheDocument();
  });

  it("shows Clear URL instead of reverting to Paste when a check fails", async () => {
    mockedApi.checkLink.mockRejectedValue(new Error("Invalid link or private video"));
    const user = userEvent.setup({ delay: null });
    renderHomePage();

    const input = screen.getByPlaceholderText("Copy and Paste your url");
    await user.type(input, "https://instagram.com/p/broken");

    await waitFor(() => expect(mockedApi.checkLink).toHaveBeenCalled());
    await screen.findByText("Clear URL");
    expect(screen.queryByText("Paste")).not.toBeInTheDocument();
    expect(input).toHaveValue("https://instagram.com/p/broken");
  });

  it("ignores a stale check response that resolves after the user cancelled and checked a different URL", async () => {
    let resolveStale: (value: VideoInfo) => void = () => {};
    const stalePromise = new Promise<VideoInfo>((resolve) => {
      resolveStale = resolve;
    });
    mockedApi.checkLink.mockImplementationOnce(() => stalePromise);
    mockedApi.checkLink.mockImplementationOnce(() => Promise.resolve(VIDEO_B));

    const user = userEvent.setup({ delay: null });
    renderHomePage();
    const input = screen.getByPlaceholderText("Copy and Paste your url");

    await user.type(input, "https://youtube.com/watch?v=stale");
    await waitFor(() => expect(mockedApi.checkLink).toHaveBeenCalledTimes(1));
    await screen.findByText(/checking link/i);

    // user gives up on the stale check (input is disabled while checking, so
    // cancelling is the only way to get a fresh, editable input again)
    await user.click(screen.getByRole("button", { name: /cancel/i }));

    await user.type(input, "https://youtube.com/watch?v=fresh");
    await waitFor(() => expect(mockedApi.checkLink).toHaveBeenCalledTimes(2));
    await screen.findByText("Video B", undefined, { timeout: 3000 });

    // the stale request now resolves after the newer one already won
    resolveStale(VIDEO_A);
    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(screen.queryByText("Video A")).not.toBeInTheDocument();
    expect(screen.getByText("Video B")).toBeInTheDocument();
  });

  it("disables Clear URL while a download is in progress, so it can't orphan the job mid-download", async () => {
    mockedApi.checkLink.mockResolvedValue(VIDEO_A);
    mockedApi.startDownload.mockResolvedValue({ job_id: "job-123" });
    mockedApi.getProgress.mockResolvedValue(RUNNING_PROGRESS);

    const user = userEvent.setup({ delay: null });
    renderHomePage();

    const input = screen.getByPlaceholderText("Copy and Paste your url");
    await user.type(input, "https://youtube.com/watch?v=abc");
    await screen.findByText("Video A", undefined, { timeout: 3000 });

    expect(screen.getByText("Clear URL").closest("button")).not.toBeDisabled();

    await user.click(screen.getByRole("button", { name: /start download/i }));

    // wait until the progress poller has picked up the job, proving downloadState is "downloading"
    await waitFor(() => expect(mockedApi.getProgress).toHaveBeenCalledWith("job-123"));

    expect(screen.getByText("Clear URL").closest("button")).toBeDisabled();

    await user.click(screen.getByText("Clear URL"));
    expect(mockedApi.cancelJob).not.toHaveBeenCalled();
  });

  it("disables the video quality selector while a download is in progress", async () => {
    mockedApi.checkLink.mockResolvedValue(VIDEO_A);
    mockedApi.startDownload.mockResolvedValue({ job_id: "job-456" });
    mockedApi.getProgress.mockResolvedValue(RUNNING_PROGRESS);

    const user = userEvent.setup({ delay: null });
    renderHomePage();

    const input = screen.getByPlaceholderText("Copy and Paste your url");
    await user.type(input, "https://youtube.com/watch?v=abc");
    await screen.findByText("Video A", undefined, { timeout: 3000 });

    expect(document.querySelector(".ant-segmented-disabled")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /start download/i }));
    await waitFor(() => expect(mockedApi.getProgress).toHaveBeenCalledWith("job-456"));

    expect(document.querySelector(".ant-segmented-disabled")).toBeInTheDocument();
  });

  it("pastes the URL by reading the clipboard through the server, not the browser API", async () => {
    mockedApi.getClipboard.mockResolvedValue({ text: "https://youtube.com/watch?v=abc  " });
    mockedApi.checkLink.mockResolvedValue(VIDEO_A);

    const user = userEvent.setup({ delay: null });
    renderHomePage();

    await user.click(screen.getByText("Paste"));

    await waitFor(() => expect(mockedApi.getClipboard).toHaveBeenCalled());
    const input = screen.getByPlaceholderText<HTMLInputElement>("Copy and Paste your url");
    await waitFor(() => expect(input.value).toBe("https://youtube.com/watch?v=abc"));
  });

  it("focuses the URL input and shows the server's error when the clipboard read fails", async () => {
    mockedApi.getClipboard.mockRejectedValue(new Error("Could not read clipboard"));

    const user = userEvent.setup({ delay: null });
    renderHomePage();

    await user.click(screen.getByText("Paste"));

    await waitFor(() => expect(mockedApi.getClipboard).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByPlaceholderText("Copy and Paste your url")).toHaveFocus());
    await screen.findByText("Could not read clipboard");
  });
});

describe("HomePage in remote mode (non-local hostname)", () => {
  const originalLocation = window.location;

  beforeEach(() => {
    vi.clearAllMocks();
    mockedApi.cancelJob.mockResolvedValue({ ok: true });
    Object.defineProperty(window, "location", {
      value: { ...originalLocation, hostname: "example.com" },
      writable: true,
      configurable: true,
    });
  });

  afterEach(() => {
    Object.defineProperty(window, "location", {
      value: originalLocation,
      writable: true,
      configurable: true,
    });
  });

  it("reads the clipboard via the browser API instead of the server", async () => {
    const user = userEvent.setup({ delay: null });
    // must be set after userEvent.setup(), which installs its own
    // navigator.clipboard stub that would otherwise clobber this one
    const readText = vi.fn().mockResolvedValue("https://youtube.com/watch?v=abc  ");
    Object.defineProperty(navigator, "clipboard", { value: { readText }, writable: true, configurable: true });

    renderHomePage();
    await user.click(screen.getByText("Paste"));

    await waitFor(() => expect(readText).toHaveBeenCalled());
    expect(mockedApi.getClipboard).not.toHaveBeenCalled();
    const input = screen.getByPlaceholderText<HTMLInputElement>("Copy and Paste your url");
    await waitFor(() => expect(input.value).toBe("https://youtube.com/watch?v=abc"));
  });

  it("shows a Download link instead of Open Folder after a finished download", async () => {
    mockedApi.checkLink.mockResolvedValue(VIDEO_A);
    mockedApi.startDownload.mockResolvedValue({ job_id: "job-789" });
    mockedApi.getProgress.mockResolvedValue({
      status: "done",
      percent: 100,
      text: "Saved: clip.mp4",
      filename: "clip.mp4",
    });

    const user = userEvent.setup({ delay: null });
    renderHomePage();

    const input = screen.getByPlaceholderText("Copy and Paste your url");
    await user.type(input, "https://youtube.com/watch?v=abc");
    await screen.findByText("Video A", undefined, { timeout: 3000 });
    await user.click(screen.getByRole("button", { name: /start download/i }));

    const downloadLink = await screen.findByText("Download");
    expect(downloadLink.closest("a")).toHaveAttribute("href", "/api/download-file/job-789");
    expect(screen.queryByText("Open Folder")).not.toBeInTheDocument();
  });
});

describe("HomePage with a playlist result", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedApi.cancelJob.mockResolvedValue({ ok: true });
  });

  it("batch-downloads every item via Download All, showing per-row status inline", async () => {
    mockedApi.checkLink.mockResolvedValue(YT_PLAYLIST);
    mockedApi.startBatchDownload.mockResolvedValue({ job_id: "job-pl" });
    mockedApi.getProgress.mockResolvedValue({
      status: "running",
      percent: 70,
      text: "",
      filename: null,
      item: 1,
      total: 2,
      saved_count: 1,
      items_progress: [
        { title: "Playlist Video 1", status: "downloading", percent: 40 },
        { title: "Playlist Video 2", status: "done", percent: 100 },
      ],
    });

    const user = userEvent.setup({ delay: null });
    renderHomePage();

    const input = screen.getByPlaceholderText("Copy and Paste your url");
    await user.type(input, "https://youtube.com/playlist?list=PLxyz");

    await screen.findByText("Playlist Video 1", undefined, { timeout: 3000 });
    expect(screen.getByText(/total items/i)).toBeInTheDocument();

    // "Download All" grabs every available, not-yet-downloaded item.
    await user.click(screen.getByRole("button", { name: /download all/i }));

    await waitFor(() =>
      expect(mockedApi.startBatchDownload).toHaveBeenCalledWith("https://youtube.com/playlist?list=PLxyz", "Best", [
        { title: "Playlist Video 1", url: "https://youtube.com/watch?v=v1", entryIndex: undefined },
        { title: "Playlist Video 2", url: "https://youtube.com/watch?v=v2", entryIndex: undefined },
      ])
    );

    // Per-row status shows inline in the list from the poll.
    await screen.findByText(/40% Downloading/i); // row 1
    await screen.findByText("Downloaded"); // row 2
    // While a batch runs, the global footer shows overall progress + Cancel Download.
    expect(screen.getByText(/1\/2 Downloaded/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /cancel download/i })).toBeInTheDocument();
  });

  it("renders a real 10-item YouTube Mix response (owner-reported 'no result' repro)", async () => {
    mockedApi.checkLink.mockResolvedValue(REAL_YOUTUBE_MIX);
    const user = userEvent.setup({ delay: null });
    renderHomePage();

    const input = screen.getByPlaceholderText("Copy and Paste your url");
    await user.type(input, "https://www.youtube.com/watch?v=dwWOEA00K8s&list=RDKzl6cT_u7RA&index=6");

    await waitFor(
      () =>
        expect(mockedApi.checkLink).toHaveBeenCalledWith(
          "https://www.youtube.com/watch?v=dwWOEA00K8s&list=RDKzl6cT_u7RA&index=6"
        ),
      { timeout: 2000 }
    );

    await screen.findByText(
      "Xa Muôn Trùng Mây | Khánh Phương | Official Music Video",
      undefined,
      { timeout: 3000 }
    );
    expect(screen.getByText(/total items/i)).toBeInTheDocument();
    expect(screen.getByText("10")).toBeInTheDocument();
    expect(screen.getByText("LIVE | Đến Sau - Ưng Hoàng Phúc | iTV HD - VTC13")).toBeInTheDocument();
    expect(screen.getByText("Yêu Cô Bạn Thân - Bằng Cường [Official MV HD]")).toBeInTheDocument();
  });

  it("downloads a single row via its own inline download button", async () => {
    mockedApi.checkLink.mockResolvedValue(YT_PLAYLIST);
    mockedApi.startBatchDownload.mockResolvedValue({ job_id: "job-one" });
    mockedApi.getProgress.mockResolvedValue({
      status: "running", percent: 10, text: "", filename: null, item: 0, total: 1, saved_count: 0,
      items_progress: [{ title: "Playlist Video 2", status: "downloading", percent: 10 }],
    });

    const user = userEvent.setup({ delay: null });
    renderHomePage();

    const input = screen.getByPlaceholderText("Copy and Paste your url");
    await user.type(input, "https://youtube.com/playlist?list=PLxyz");
    await screen.findByText("Playlist Video 1", undefined, { timeout: 3000 });

    // Each row has its own download button; clicking one downloads just that item.
    const rowButtons = screen.getAllByLabelText("download-item");
    expect(rowButtons).toHaveLength(2);
    await user.click(rowButtons[1]);

    await waitFor(() =>
      expect(mockedApi.startBatchDownload).toHaveBeenCalledWith("https://youtube.com/playlist?list=PLxyz", "Best", [
        { title: "Playlist Video 2", url: "https://youtube.com/watch?v=v2", entryIndex: undefined },
      ])
    );
  });

  it("renders a 1-item playlist as a plain single video and downloads that item's URL", async () => {
    mockedApi.checkLink.mockResolvedValue(YT_PLAYLIST_SINGLE);
    mockedApi.startDownload.mockResolvedValue({ job_id: "job-solo" });
    mockedApi.getProgress.mockResolvedValue(RUNNING_PROGRESS);

    const user = userEvent.setup({ delay: null });
    renderHomePage();

    const input = screen.getByPlaceholderText("Copy and Paste your url");
    await user.type(input, "https://youtube.com/playlist?list=PLsolo");
    await screen.findByText("Solo Video", undefined, { timeout: 3000 });

    // Rendered as a plain single video, not the playlist list (no "Total Items").
    expect(screen.queryByText(/total items/i)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /start download/i }));
    await waitFor(() =>
      expect(mockedApi.startDownload).toHaveBeenCalledWith("https://youtube.com/watch?v=solo", "Solo Video", "Best", undefined)
    );
  });

  it("hides unavailable videos, reveals them via the filter, and Download All skips them", async () => {
    mockedApi.checkLink.mockResolvedValue(YT_PLAYLIST_WITH_DEAD);
    mockedApi.startBatchDownload.mockResolvedValue({ job_id: "job-dead" });
    mockedApi.getProgress.mockResolvedValue(BATCH_RUNNING);

    const user = userEvent.setup({ delay: null });
    renderHomePage();

    const input = screen.getByPlaceholderText("Copy and Paste your url");
    await user.type(input, "https://youtube.com/playlist?list=PLdead");

    await screen.findByText("Good One", undefined, { timeout: 3000 });
    // The [Private video] is hidden by default; the other available one shows.
    expect(screen.queryByText("[Private video]")).not.toBeInTheDocument();
    expect(screen.getByText("Good Two")).toBeInTheDocument();

    // Flip the "Show unavailable videos" filter -> the dead video appears (still unselectable).
    await user.click(screen.getByRole("switch"));
    expect(screen.getByText("[Private video]")).toBeInTheDocument();

    // Download All targets ONLY the 2 available videos (skips the dead one).
    await user.click(screen.getByRole("button", { name: /download all/i }));
    await waitFor(() =>
      expect(mockedApi.startBatchDownload).toHaveBeenCalledWith("https://youtube.com/playlist?list=PLdead", "Best", [
        { title: "Good One", url: "u1", entryIndex: undefined },
        { title: "Good Two", url: "u3", entryIndex: undefined },
      ])
    );
  });

  it("batch-downloads Instagram Story items by their entry index", async () => {
    mockedApi.checkLink.mockResolvedValue(PLAYLIST_RESULT);
    mockedApi.startBatchDownload.mockResolvedValue({ job_id: "job-story" });
    mockedApi.getProgress.mockResolvedValue(BATCH_RUNNING);

    const user = userEvent.setup({ delay: null });
    renderHomePage();

    const input = screen.getByPlaceholderText("Copy and Paste your url");
    await user.type(input, "https://www.instagram.com/stories/someone/1/");

    await screen.findByText("Story item 1", undefined, { timeout: 3000 });
    await user.click(screen.getByRole("button", { name: /download all/i }));

    await waitFor(() =>
      expect(mockedApi.startBatchDownload).toHaveBeenCalledWith("https://www.instagram.com/stories/someone/1/", "720p", [
        { title: "Story item 1", url: undefined, entryIndex: 1 },
        { title: "Story item 2", url: undefined, entryIndex: 2 },
      ])
    );
  });

  it("shows the empty-state message when the playlist has no video items", async () => {
    mockedApi.checkLink.mockResolvedValue({ ...PLAYLIST_RESULT, items: [] });

    const user = userEvent.setup({ delay: null });
    renderHomePage();

    const input = screen.getByPlaceholderText("Copy and Paste your url");
    await user.type(input, "https://www.instagram.com/stories/someone/1/");

    await screen.findByText(/no downloadable video/i, undefined, { timeout: 3000 });
  });
});

describe("HomePage with Instagram photos", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedApi.cancelJob.mockResolvedValue({ ok: true });
  });

  it("downloads a single photo with no quality picker shown", async () => {
    mockedApi.checkLink.mockResolvedValue(IG_PHOTO);
    mockedApi.startDownload.mockResolvedValue({ job_id: "job-photo" });
    mockedApi.getProgress.mockResolvedValue(RUNNING_PROGRESS);

    const user = userEvent.setup({ delay: null });
    renderHomePage();

    const input = screen.getByPlaceholderText("Copy and Paste your url");
    await user.type(input, "https://www.instagram.com/p/abc/");
    await screen.findByText("A nice photo", undefined, { timeout: 3000 });

    // A single "Image" quality has nothing to choose - no segmented picker.
    expect(document.querySelector(".ant-segmented")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /start download/i }));

    await waitFor(() =>
      expect(mockedApi.startDownload).toHaveBeenCalledWith("https://www.instagram.com/p/abc/", "A nice photo", "Image", undefined)
    );
  });

  it("shows photo/video badges and batch-downloads the selected carousel slides", async () => {
    mockedApi.checkLink.mockResolvedValue(IG_CAROUSEL);
    mockedApi.startBatchDownload.mockResolvedValue({ job_id: "job-slide" });
    mockedApi.getProgress.mockResolvedValue({ ...BATCH_RUNNING, total: 1 });

    const user = userEvent.setup({ delay: null });
    renderHomePage();

    const input = screen.getByPlaceholderText("Copy and Paste your url");
    await user.type(input, "https://www.instagram.com/p/abc/");

    await screen.findByText("Slide 1", undefined, { timeout: 3000 });
    expect(screen.getByText("Photo")).toBeInTheDocument();
    expect(screen.getByText("Video")).toBeInTheDocument();
    // A mixed image/video carousel has single-option qualities -> no quality picker.
    expect(document.querySelector(".ant-segmented")).not.toBeInTheDocument();

    // Ticking a row (its title) surfaces the manual "Download Items Selected" button.
    await user.click(screen.getByText("Slide 2"));
    await user.click(screen.getByRole("button", { name: /download items selected/i }));

    await waitFor(() =>
      expect(mockedApi.startBatchDownload).toHaveBeenCalledWith("https://www.instagram.com/p/abc/", "Best", [
        { title: "Slide 2", url: undefined, entryIndex: 2 },
      ])
    );
  });
});
