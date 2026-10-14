import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import SettingsPage from "./SettingsPage";
import { api } from "../api";
import { reloadFresh } from "../lib/clearData";
import { LanguageProvider } from "../i18n/LanguageContext";

vi.mock("../api", () => ({
  api: {
    getSettings: vi.fn(),
    updateSettings: vi.fn(),
    browseFolder: vi.fn(),
    browseFile: vi.fn(),
    clearSession: vi.fn(),
  },
}));

vi.mock("../lib/clearData", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../lib/clearData")>()),
  reloadFresh: vi.fn(),
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

  it("lists the Chrome profiles for YouTube sign-in, off by default, and saves the choice", async () => {
    mockedApi.getSettings.mockResolvedValue({
      path: "/Users/test/Downloads",
      cookies_path: "",
      cookies_status: "none",
      youtube_cookie_source: "",
      youtube_profiles: [
        { id: "Default", name: "Default" },
        { id: "Profile 2", name: "Work" },
      ],
    });
    const user = userEvent.setup({ delay: null });
    renderSettingsPage();

    expect(await screen.findByText("YouTube sign-in")).toBeInTheDocument();
    expect(await screen.findByRole("radio", { name: "Work · Profile 2" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Off" })).toBeChecked();

    await user.click(screen.getByRole("radio", { name: "Work · Profile 2" }));
    expect(mockedApi.updateSettings).toHaveBeenCalledWith({ youtube_cookie_source: "chrome:Profile 2" });

    await user.click(screen.getByRole("radio", { name: "Off" }));
    expect(mockedApi.updateSettings).toHaveBeenLastCalledWith({ youtube_cookie_source: "" });
  });

  it("shows the saved Chrome profile as selected and says so when Chrome has no profile", async () => {
    mockedApi.getSettings.mockResolvedValue({
      path: "/x",
      cookies_path: "",
      cookies_status: "none",
      youtube_cookie_source: "chrome:Default",
      youtube_profiles: [{ id: "Default", name: "Default" }],
    });
    const { unmount } = renderSettingsPage();
    await waitFor(() => expect(screen.getByRole("radio", { name: "Default" })).toBeChecked());
    unmount();

    mockedApi.getSettings.mockResolvedValue({ path: "/x", cookies_path: "", cookies_status: "none", youtube_profiles: [] });
    renderSettingsPage();
    expect(await screen.findByText("No Chrome profile found on this Mac.")).toBeInTheDocument();
  });

  it("goes back to the previous choice if saving the YouTube sign-in fails", async () => {
    mockedApi.getSettings.mockResolvedValue({
      path: "/x",
      cookies_path: "",
      cookies_status: "none",
      youtube_cookie_source: "",
      youtube_profiles: [{ id: "Default", name: "Default" }],
    });
    mockedApi.updateSettings.mockRejectedValue(new Error("nope"));
    const user = userEvent.setup({ delay: null });
    renderSettingsPage();

    await user.click(await screen.findByRole("radio", { name: "Default" }));
    await waitFor(() => expect(screen.getByRole("radio", { name: "Off" })).toBeChecked());
  });

  it("loads the configured download path from the server", async () => {
    renderSettingsPage();
    await waitFor(() => expect(mockedApi.getSettings).toHaveBeenCalled());
    expect(await screen.findByDisplayValue("/Users/test/Downloads")).toBeInTheDocument();
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

  it("hides Target Path but keeps Language", () => {
    renderSettingsPage();

    expect(screen.queryByText("Target Path")).not.toBeInTheDocument();
    expect(screen.getByText("Language")).toBeInTheDocument();
  });

  it("hides the YouTube sign-in section (reading a browser's cookies is a Mac-only thing)", () => {
    renderSettingsPage();
    expect(screen.queryByText("YouTube sign-in")).not.toBeInTheDocument();
  });

  describe("Clear cache and saved data", () => {
    it("asks first, and does nothing when the user says no", async () => {
      const user = userEvent.setup({ delay: null });
      vi.spyOn(window, "confirm").mockReturnValue(false);
      localStorage.setItem("omniflow-history", "[1]");
      renderSettingsPage();
      await user.click(screen.getByRole("button", { name: "Clear cache and saved data" }));
      expect(mockedApi.clearSession).not.toHaveBeenCalled();
      expect(localStorage.getItem("omniflow-history")).toBe("[1]");
      expect(reloadFresh).not.toHaveBeenCalled();
    });

    it("on yes: clears the server side, wipes the saved data and reloads fresh - even if the server call fails", async () => {
      const user = userEvent.setup({ delay: null });
      vi.spyOn(window, "confirm").mockReturnValue(true);
      mockedApi.clearSession.mockRejectedValue(new Error("offline"));
      localStorage.setItem("omniflow-history", "[1]");
      renderSettingsPage();
      await user.click(screen.getByRole("button", { name: "Clear cache and saved data" }));
      await waitFor(() => expect(reloadFresh).toHaveBeenCalledTimes(1));
      expect(mockedApi.clearSession).toHaveBeenCalledTimes(1);
      expect(localStorage.length).toBe(0);
    });

    it("is offered in Vietnamese too", async () => {
      const user = userEvent.setup({ delay: null });
      renderSettingsPage();
      await user.click(screen.getByRole("radio", { name: "Vietnamese" }));
      expect(screen.getByRole("button", { name: "Xoá bộ nhớ đệm và dữ liệu đã lưu" })).toBeInTheDocument();
    });
  });
});
