import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import HomePage from "./HomePage";
import { api } from "../api";
import { LanguageProvider } from "../i18n/LanguageContext";
import type { Page } from "../components/Header";
import type { JobProgress, VideoInfo } from "../types";

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
    getProgress: vi.fn(),
    cancelJob: vi.fn(),
    openFolder: vi.fn(),
    getClipboard: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api, true);

const VIDEO_A: VideoInfo = {
  title: "Video A",
  uploader: "Uploader A",
  thumbnail: null,
  platform: "YouTube",
  qualities: ["720p", "360p", "Best", "Audio Only"],
  duration: "01:00",
};

const VIDEO_B: VideoInfo = {
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
