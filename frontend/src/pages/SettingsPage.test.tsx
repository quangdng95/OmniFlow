import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import SettingsPage from "./SettingsPage";
import { api } from "../api";
import { LanguageProvider } from "../i18n/LanguageContext";

vi.mock("../api", () => ({
  api: {
    getSettings: vi.fn(),
    updateSettings: vi.fn(),
    browseFolder: vi.fn(),
    browseFile: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api, true);

const renderSettingsPage = () =>
  render(
    <LanguageProvider>
      <SettingsPage onNavigate={vi.fn()} />
    </LanguageProvider>
  );

describe("SettingsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    mockedApi.getSettings.mockResolvedValue({ path: "/Users/test/Downloads", cookies_path: "", cookies_status: "none" });
    mockedApi.updateSettings.mockResolvedValue({ path: "/Users/test/Downloads", cookies_path: "", cookies_status: "none" });
  });

  it("renders in English by default and has no notification section", () => {
    renderSettingsPage();

    expect(screen.getByText("Target Path")).toBeInTheDocument();
    expect(screen.getByText("Language")).toBeInTheDocument();
    expect(screen.queryByText("Notification")).not.toBeInTheDocument();
    expect(screen.queryByText(/send test notification/i)).not.toBeInTheDocument();
  });

  it("switches the whole page to Vietnamese immediately when the Vietnamese option is selected", async () => {
    const user = userEvent.setup({ delay: null });
    renderSettingsPage();

    await user.click(screen.getByRole("radio", { name: "Vietnamese" }));

    expect(screen.getByText("Thư mục lưu")).toBeInTheDocument();
    expect(screen.getByText("Ngôn ngữ")).toBeInTheDocument();
    expect(screen.queryByText("Target Path")).not.toBeInTheDocument();
  });

  it("persists the selected language so it survives a remount", async () => {
    const user = userEvent.setup({ delay: null });
    const { unmount } = renderSettingsPage();

    await user.click(screen.getByRole("radio", { name: "Vietnamese" }));
    expect(localStorage.getItem("omniflow-language")).toBe("vi");
    unmount();

    renderSettingsPage();
    await waitFor(() => expect(screen.getByText("Ngôn ngữ")).toBeInTheDocument());
  });

  it("loads the configured download path from the server", async () => {
    renderSettingsPage();
    await waitFor(() => expect(mockedApi.getSettings).toHaveBeenCalled());
    expect(await screen.findByDisplayValue("/Users/test/Downloads")).toBeInTheDocument();
  });

  it("lets the user pick and later remove an Instagram cookies file", async () => {
    mockedApi.browseFile.mockResolvedValue({ path: "/Users/test/cookies.txt", cookies_status: "valid" });
    const user = userEvent.setup({ delay: null });
    renderSettingsPage();

    expect(screen.queryByText("Remove")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /select file/i }));

    await waitFor(() => expect(mockedApi.updateSettings).toHaveBeenCalledWith({ cookies_path: "/Users/test/cookies.txt" }));
    expect(await screen.findByDisplayValue("/Users/test/cookies.txt")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Remove" }));
    await waitFor(() => expect(mockedApi.updateSettings).toHaveBeenCalledWith({ cookies_path: "" }));
    expect(screen.queryByDisplayValue("/Users/test/cookies.txt")).not.toBeInTheDocument();
  });

  it("shows no cookies status hint by default", () => {
    renderSettingsPage();

    expect(screen.queryByText(/session cookie found/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/doesn't look like it has an instagram session/i)).not.toBeInTheDocument();
  });

  it("warns when the picked cookies file has no detectable Instagram session", async () => {
    mockedApi.browseFile.mockResolvedValue({ path: "/Users/test/cookies.txt", cookies_status: "no_session" });
    const user = userEvent.setup({ delay: null });
    renderSettingsPage();

    await user.click(screen.getByRole("button", { name: /select file/i }));

    expect(await screen.findByText(/doesn't look like it has an instagram session/i)).toBeInTheDocument();
  });

  it("confirms when the picked cookies file has a detectable Instagram session", async () => {
    mockedApi.browseFile.mockResolvedValue({ path: "/Users/test/cookies.txt", cookies_status: "valid" });
    const user = userEvent.setup({ delay: null });
    renderSettingsPage();

    await user.click(screen.getByRole("button", { name: /select file/i }));

    expect(await screen.findByText(/session cookie found/i)).toBeInTheDocument();
  });

  it("clears the status hint after removing the cookies file", async () => {
    mockedApi.browseFile.mockResolvedValue({ path: "/Users/test/cookies.txt", cookies_status: "valid" });
    const user = userEvent.setup({ delay: null });
    renderSettingsPage();

    await user.click(screen.getByRole("button", { name: /select file/i }));
    expect(await screen.findByText(/session cookie found/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Remove" }));
    expect(screen.queryByText(/session cookie found/i)).not.toBeInTheDocument();
  });
});

describe("SettingsPage in remote mode (non-local hostname)", () => {
  const originalLocation = window.location;

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    mockedApi.getSettings.mockResolvedValue({ path: "/Users/test/Downloads", cookies_path: "", cookies_status: "none" });
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

  it("hides Target Path and Instagram Cookies but keeps Language", () => {
    renderSettingsPage();

    expect(screen.queryByText("Target Path")).not.toBeInTheDocument();
    expect(screen.queryByText("Instagram Cookies (optional)")).not.toBeInTheDocument();
    expect(screen.getByText("Language")).toBeInTheDocument();
  });
});
