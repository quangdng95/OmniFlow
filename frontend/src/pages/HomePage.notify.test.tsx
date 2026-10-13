import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import HomePage from "./HomePage";
import { api } from "../api";
import { resetNotifyPermissionAsked } from "../lib/notify";
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

const VIDEO: VideoInfo = {
  type: "video", title: "Video A", uploader: "U", thumbnail: null, platform: "YouTube",
  qualities: ["Best"], duration: "01:00",
};
const PLAYLIST: PlaylistCheckResult = {
  type: "playlist", platform: "YouTube", title: "My Playlist",
  items: [
    { id: "1", title: "One", position: 1, thumbnail: null, duration: "1:00", url: "u1", qualities: ["Best", "720p"], is_available: true },
    { id: "2", title: "Two", position: 2, thumbnail: null, duration: "1:00", url: "u2", qualities: ["Best", "720p"], is_available: true },
    { id: "3", title: "Three", position: 3, thumbnail: null, duration: "1:00", url: "u3", qualities: ["Best", "720p"], is_available: true },
  ],
};

type Perm = "default" | "granted" | "denied";
let instances: { title: string; options?: NotificationOptions }[] = [];
let requestPermission: ReturnType<typeof vi.fn>;

const installNotification = (permission: Perm, hidden: boolean) => {
  instances = [];
  requestPermission = vi.fn().mockResolvedValue("granted");
  class MockNotification {
    static permission: Perm = permission;
    static requestPermission = requestPermission;
    onclick: (() => void) | null = null;
    close = vi.fn();
    title: string;
    options?: NotificationOptions;
    constructor(title: string, options?: NotificationOptions) {
      this.title = title;
      this.options = options;
      instances.push(this);
    }
  }
  vi.stubGlobal("Notification", MockNotification);
  Object.defineProperty(document, "hidden", { configurable: true, get: () => hidden });
  Object.defineProperty(window, "isSecureContext", { configurable: true, value: true });
};

const renderHome = () =>
  render(
    <LanguageProvider>
      <HomePage onNavigate={vi.fn()} />
    </LanguageProvider>
  );

const startSingle = async () => {
  const user = userEvent.setup({ delay: null });
  renderHome();
  await user.type(screen.getByPlaceholderText("Copy and Paste your url"), "https://youtube.com/watch?v=n");
  await screen.findByText("Video A", undefined, { timeout: 3000 });
  await user.click(screen.getByRole("button", { name: /start download/i }));
};

// jsdom's hostname is localhost, i.e. the local app: a finished job is a saved file.
describe("HomePage 'saved' feedback (local app)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetNotifyPermissionAsked();
    mockedApi.checkLink.mockResolvedValue(VIDEO);
    mockedApi.startDownload.mockResolvedValue({ job_id: "j1" });
    mockedApi.cancelJob.mockResolvedValue({ ok: true });
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    Object.defineProperty(document, "hidden", { configurable: true, get: () => false });
  });

  it("visible tab: one toast with the file name, no system notification", async () => {
    installNotification("granted", false);
    mockedApi.getProgress.mockResolvedValue({ status: "done", percent: 100, text: "", filename: "clip.mp4" });
    await startSingle();
    expect(await screen.findByText("Saved to your device")).toBeInTheDocument();
    await waitFor(() => expect(screen.getAllByText("clip.mp4").length).toBeGreaterThan(0));
    expect(screen.getAllByText("Saved to your device")).toHaveLength(1);
    expect(instances).toHaveLength(0);
  });

  it("hidden tab + granted: toast and exactly one system notification", async () => {
    installNotification("granted", true);
    mockedApi.getProgress.mockResolvedValue({ status: "done", percent: 100, text: "", filename: "clip.mp4" });
    await startSingle();
    await waitFor(() => expect(instances).toHaveLength(1));
    await new Promise((r) => setTimeout(r, 1600)); // further polls must not re-notify
    expect(instances).toHaveLength(1);
    expect(instances[0].title).toBe("Saved to your device");
    expect(instances[0].options?.body).toBe("clip.mp4");
  });

  it.each<Perm>(["denied", "default"])("hidden tab + %s: toast only, silently", async (perm) => {
    installNotification(perm, true);
    mockedApi.getProgress.mockResolvedValue({ status: "done", percent: 100, text: "", filename: "clip.mp4" });
    await startSingle();
    expect(await screen.findByText("Saved to your device")).toBeInTheDocument();
    expect(instances).toHaveLength(0);
  });

  it("asks for permission on the Download click when undecided, not on load", async () => {
    installNotification("default", false);
    mockedApi.getProgress.mockResolvedValue({ status: "running", percent: 10, text: "", filename: null });
    const user = userEvent.setup({ delay: null });
    renderHome();
    expect(requestPermission).not.toHaveBeenCalled();
    await user.type(screen.getByPlaceholderText("Copy and Paste your url"), "https://youtube.com/watch?v=n");
    await screen.findByText("Video A", undefined, { timeout: 3000 });
    expect(requestPermission).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: /start download/i }));
    expect(requestPermission).toHaveBeenCalledTimes(1);
  });

  it("a failed download shows no 'saved' toast or notification", async () => {
    installNotification("granted", true);
    mockedApi.getProgress.mockResolvedValue({ status: "error", percent: 5, text: "boom", filename: null });
    await startSingle();
    await waitFor(() => expect(mockedApi.getProgress).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 300));
    expect(screen.queryByText("Saved to your device")).not.toBeInTheDocument();
    expect(instances).toHaveLength(0);
  });

  it("a cancelled download shows no 'saved' toast or notification", async () => {
    installNotification("granted", true);
    mockedApi.getProgress.mockResolvedValue({ status: "cancelled", percent: 5, text: "", filename: null });
    await startSingle();
    await waitFor(() => expect(mockedApi.getProgress).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 300));
    expect(screen.queryByText("Saved to your device")).not.toBeInTheDocument();
    expect(instances).toHaveLength(0);
  });

  it("a finished batch sends ONE combined notification with saved and failed counts", async () => {
    installNotification("granted", true);
    mockedApi.checkLink.mockResolvedValue(PLAYLIST);
    mockedApi.startBatchDownload.mockResolvedValue({ job_id: "b1" });
    mockedApi.getProgress.mockResolvedValue({
      status: "done", percent: 100, text: "", filename: null,
      items_progress: [
        { title: "One", status: "done", percent: 100 },
        { title: "Two", status: "done", percent: 100 },
        { title: "Three", status: "error", percent: 0 },
      ],
    });
    const user = userEvent.setup({ delay: null });
    renderHome();
    await user.type(screen.getByPlaceholderText("Copy and Paste your url"), "https://youtube.com/playlist?list=PL1");
    await screen.findByText("One", undefined, { timeout: 3000 });
    await user.click(screen.getByRole("button", { name: /download all/i }));
    await waitFor(() => expect(instances).toHaveLength(1));
    await new Promise((r) => setTimeout(r, 1600));
    expect(instances).toHaveLength(1);
    expect(instances[0].title).toBe("2 saved, 1 failed");
    expect(instances[0].options?.body).toBe("My Playlist");
    expect(await screen.findByText("2 saved, 1 failed")).toBeInTheDocument();
  });

  it("a cancelled batch announces nothing", async () => {
    installNotification("granted", true);
    mockedApi.checkLink.mockResolvedValue(PLAYLIST);
    mockedApi.startBatchDownload.mockResolvedValue({ job_id: "b2" });
    mockedApi.getProgress.mockResolvedValue({
      status: "cancelled", percent: 40, text: "", filename: null,
      items_progress: [{ title: "One", status: "done", percent: 100 }],
    });
    const user = userEvent.setup({ delay: null });
    renderHome();
    await user.type(screen.getByPlaceholderText("Copy and Paste your url"), "https://youtube.com/playlist?list=PL2");
    await screen.findByText("One", undefined, { timeout: 3000 });
    await user.click(screen.getByRole("button", { name: /download all/i }));
    await waitFor(() => expect(mockedApi.getProgress).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 300));
    expect(instances).toHaveLength(0);
    expect(screen.queryByText(/saved/i, { selector: "[data-sonner-toast] *" })).not.toBeInTheDocument();
  });
});
