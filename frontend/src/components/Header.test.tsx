import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import Header, { type Page } from "./Header";
import PageTitle from "./PageTitle";
import { LanguageProvider } from "../i18n/LanguageContext";

const renderHeader = (active: Page = "home", onNavigate: (page: Page) => void = vi.fn()) =>
  render(
    <LanguageProvider>
      <Header active={active} onNavigate={onNavigate} />
    </LanguageProvider>
  );

// Base UI's menu trigger listens for pointer events, which jsdom only partly
// supports, so the tests open it the way a keyboard user does (also proves it
// is operable without a mouse). The real mouse/touch path was verified
// separately in a real browser (headless Chrome, 390px and 1280px wide).
const openMenu = async (user: ReturnType<typeof userEvent.setup>) => {
  screen.getByRole("button", { name: "Menu" }).focus();
  await user.keyboard("{Enter}");
};

const originalLocation = window.location;
const useHostname = (hostname: string) =>
  Object.defineProperty(window, "location", {
    value: { ...originalLocation, hostname },
    writable: true,
    configurable: true,
  });

afterEach(() => {
  Object.defineProperty(window, "location", { value: originalLocation, writable: true, configurable: true });
});

describe("Header", () => {
  it("is one slim sticky bar: logo, language switch and a single menu button", () => {
    renderHeader();
    const header = screen.getByRole("banner");
    expect(header.className).toMatch(/sticky/);
    expect(header.className).toMatch(/top-0/);
    expect(screen.getByRole("button", { name: "Menu" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: /language/i })).toBeInTheDocument();
    // Pages live in the menu, not as a row of buttons in the bar.
    expect(screen.queryByRole("button", { name: "History" })).not.toBeInTheDocument();
    expect(screen.queryByRole("menuitem")).not.toBeInTheDocument();
  });

  it("keeps the logo at half its old size (23px icon, was 46px)", () => {
    renderHeader();
    const logo = screen.getByAltText("Logo");
    expect(logo).toHaveAttribute("width", "23");
    expect(logo).toHaveAttribute("height", "23");
  });

  it("opens a menu with every page, marking the current one", async () => {
    const user = userEvent.setup();
    renderHeader("history");
    await openMenu(user);

    const labels = screen.getAllByRole("menuitem").map((item) => item.textContent?.trim());
    expect(labels).toEqual(["Home", "History", "Changelog", "Settings", "Terms of Use"]);
    expect(screen.getByRole("menuitem", { name: "History" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("menuitem", { name: "Home" })).not.toHaveAttribute("aria-current");
  });

  it("navigates to the chosen page and closes the menu", async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    renderHeader("home", onNavigate);
    await openMenu(user);
    await user.click(screen.getByRole("menuitem", { name: "Settings" }));

    expect(onNavigate).toHaveBeenCalledWith("settings");
    await vi.waitFor(() => expect(screen.queryByRole("menuitem")).not.toBeInTheDocument());
  });

  it("takes you Home when the logo is pressed", async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    renderHeader("settings", onNavigate);
    await user.click(screen.getByRole("button", { name: "Home" }));
    expect(onNavigate).toHaveBeenCalledWith("home");
  });

  it("offers Shortcut Setup only on a remote deployment", async () => {
    const user = userEvent.setup();
    useHostname("example.com");
    renderHeader();
    await openMenu(user);
    expect(screen.getByRole("menuitem", { name: "Shortcut Setup" })).toBeInTheDocument();
  });

  it("hides Shortcut Setup on the local desktop app", async () => {
    const user = userEvent.setup();
    useHostname("localhost");
    renderHeader();
    await openMenu(user);
    expect(screen.queryByRole("menuitem", { name: "Shortcut Setup" })).not.toBeInTheDocument();
  });
});

describe("PageTitle", () => {
  it("shows the page's own title now that the header no longer does", () => {
    render(
      <LanguageProvider>
        <PageTitle page="history" />
      </LanguageProvider>
    );
    expect(screen.getByRole("heading", { level: 2, name: "History" })).toBeInTheDocument();
  });
});
