import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import TermsPage from "./TermsPage";
import ChangelogPage from "./ChangelogPage";
import ShortcutSetupPage from "./ShortcutSetupPage";
import LoginPage from "./LoginPage";
import { LanguageProvider } from "../i18n/LanguageContext";
import { translations } from "../i18n/translations";

const wrap = (ui: React.ReactElement) => render(<LanguageProvider>{ui}</LanguageProvider>);

describe("Terms page", () => {
  it("renders the heading, intro and every section in English", () => {
    wrap(<TermsPage onNavigate={vi.fn()} />);
    const terms = translations.en.terms;
    expect(screen.getByText(terms.heading)).toBeInTheDocument();
    for (const section of terms.sections) expect(screen.getByText(section.heading)).toBeInTheDocument();
  });

  it("has no hard-coded palette left: text uses the ink tokens, body copy is >= 16px", () => {
    const { container } = wrap(<TermsPage onNavigate={vi.fn()} />);
    const html = container.innerHTML;
    expect(html).not.toMatch(/slate-|neutral-|#0d9585|text-xs|text-sm/);
  });
});

describe("Changelog page", () => {
  it("renders without crashing and lists dated entries", () => {
    wrap(<ChangelogPage onNavigate={vi.fn()} />);
    expect(screen.getAllByText(/20\d\d-\d\d-\d\d/).length).toBeGreaterThan(0);
  });
});

describe("Shortcut setup page", () => {
  it("renders the guide with the site's own origin to copy", () => {
    wrap(<ShortcutSetupPage onNavigate={vi.fn()} />);
    expect(screen.getAllByText(window.location.origin, { exact: false }).length).toBeGreaterThan(0);
  });
});

describe("Login page", () => {
  const fetchMock = vi.fn();
  const originalLocation = window.location;

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
    Object.defineProperty(window, "location", {
      value: { ...originalLocation, assign: vi.fn() },
      writable: true,
      configurable: true,
    });
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    Object.defineProperty(window, "location", { value: originalLocation, writable: true, configurable: true });
  });

  it("keeps Unlock disabled until a token is typed", async () => {
    wrap(<LoginPage />);
    expect(screen.getByRole("button", { name: "Unlock" })).toBeDisabled();
    await userEvent.setup().type(screen.getByLabelText("Access token"), "abc");
    expect(screen.getByRole("button", { name: "Unlock" })).toBeEnabled();
  });

  it("hides the token until asked to show it", async () => {
    wrap(<LoginPage />);
    const field = screen.getByLabelText("Access token");
    expect(field).toHaveAttribute("type", "password");
    await userEvent.setup().click(screen.getByRole("button", { name: "Show token" }));
    expect(field).toHaveAttribute("type", "text");
  });

  it("posts the token (never in the URL) and goes to / on success", async () => {
    fetchMock.mockResolvedValue({ ok: true, status: 200 });
    const user = userEvent.setup();
    wrap(<LoginPage />);
    await user.type(screen.getByLabelText("Access token"), "secret");
    await user.click(screen.getByRole("button", { name: "Unlock" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/unlock");
    expect(String(init.body)).toContain("token=secret");
    await waitFor(() => expect(window.location.assign).toHaveBeenCalledWith("/"));
  });

  it.each([
    [401, "Incorrect token. Please try again."],
    [429, "Too many attempts. Try again in a few minutes."],
  ])("HTTP %i shows the matching message", async (status, message) => {
    fetchMock.mockResolvedValue({ ok: false, status });
    const user = userEvent.setup();
    wrap(<LoginPage />);
    await user.type(screen.getByLabelText("Access token"), "nope");
    await user.click(screen.getByRole("button", { name: "Unlock" }));
    expect(await screen.findByText(message)).toBeInTheDocument();
  });

  it("a network failure shows the connection message", async () => {
    fetchMock.mockRejectedValue(new Error("offline"));
    const user = userEvent.setup();
    wrap(<LoginPage />);
    await user.type(screen.getByLabelText("Access token"), "x");
    await user.click(screen.getByRole("button", { name: "Unlock" }));
    expect(await screen.findByText(/Could not reach the server/)).toBeInTheDocument();
  });

  it("submitting with Enter works too", async () => {
    fetchMock.mockResolvedValue({ ok: true, status: 200 });
    const user = userEvent.setup();
    wrap(<LoginPage />);
    await user.type(screen.getByLabelText("Access token"), "k{Enter}");
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    fireEvent.blur(screen.getByLabelText("Access token"));
  });
});
