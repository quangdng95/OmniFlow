import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { api } from "./api";

vi.mock("./api", () => ({
  api: {
    getSettings: vi.fn(),
    updateSettings: vi.fn(),
    browseFolder: vi.fn(),
    browseFile: vi.fn(),
    checkLink: vi.fn(),
    getClipboard: vi.fn(),
    cancelJob: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api, true);

const openMenuItem = async (user: ReturnType<typeof userEvent.setup>, name: string) => {
  screen.getByRole("button", { name: "Menu" }).focus();
  await user.keyboard("{Enter}");
  await user.click(await screen.findByRole("menuitem", { name }));
};

describe("App", () => {
  beforeEach(() => {
    localStorage.clear();
    window.history.pushState({}, "", "/");
    mockedApi.getSettings.mockResolvedValue({ path: "/Users/t/Downloads", cookies_path: "", cookies_status: "none" });
    mockedApi.getClipboard.mockRejectedValue(new Error("no clipboard"));
  });

  it("renders the whole home layout: header, hero, URL bar, footer", () => {
    render(<App />);
    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Paste a link.");
    expect(screen.getByLabelText("Video link")).toBeInTheDocument();
    expect(screen.getByRole("contentinfo")).toBeInTheDocument();
  });

  it("opens Terms from the footer link and shows its title", async () => {
    render(<App />);
    await userEvent.setup().click(within(screen.getByRole("contentinfo")).getByRole("button", { name: "Terms of Use" }));
    expect(await screen.findByRole("heading", { level: 2, name: "Terms of Use" })).toBeInTheDocument();
  });

  it.each([
    ["History", "History"],
    ["Changelog", "Changelog"],
    ["Settings", "Settings"],
  ])("menu → %s opens that page under its own title", async (item, title) => {
    const user = userEvent.setup();
    render(<App />);
    await openMenuItem(user, item);
    expect(await screen.findByRole("heading", { level: 2, name: title })).toBeInTheDocument();
  });

  it("the logo takes you back Home, and Home keeps what you typed", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.type(screen.getByLabelText("Video link"), "https://youtube.com/watch?v=a");
    await openMenuItem(user, "Settings");
    await screen.findByRole("heading", { level: 2, name: "Settings" });
    await user.click(screen.getByRole("button", { name: "Home" }));
    expect(screen.getByLabelText("Video link")).toHaveValue("https://youtube.com/watch?v=a");
  });

  it("switching to Vietnamese relabels the whole page and the document language", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("button", { name: /vietnam|tiếng việt/i }));
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Dán link.");
    expect(screen.getByRole("button", { name: "Điều khoản sử dụng" })).toBeInTheDocument();
    expect(document.documentElement.lang).toBe("vi");
  });

  it("/unlock shows the sign-in screen instead of the app", () => {
    window.history.pushState({}, "", "/unlock");
    render(<App />);
    expect(screen.queryByRole("banner")).not.toBeInTheDocument();
    expect(screen.getByText("Welcome to OmniFlow")).toBeInTheDocument();
  });
});
