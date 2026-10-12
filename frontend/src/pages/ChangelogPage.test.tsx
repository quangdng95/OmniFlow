import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ChangelogPage from "./ChangelogPage";
import LanguageSwitcher from "../components/LanguageSwitcher";
import { LanguageProvider } from "../i18n/LanguageContext";
import { translations } from "../i18n/translations";

const renderPage = () =>
  render(
    <LanguageProvider>
      <LanguageSwitcher />
      <ChangelogPage onNavigate={vi.fn()} />
    </LanguageProvider>
  );

describe("ChangelogPage", () => {
  beforeEach(() => localStorage.clear());

  it("shows only the release log: no eyebrow, no heading, no intro paragraph", () => {
    const { container } = renderPage();
    expect(screen.queryByText(/what's new/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/What's changed in Vidrop/)).not.toBeInTheDocument();
    expect(screen.queryByText(/running log of what actually shipped/)).not.toBeInTheDocument();
    expect(container.querySelector("h3")).toBeNull();
    expect(container.querySelectorAll("ul")).toHaveLength(translations.en.changelog.releases.length);
  });

  it("has dropped the removed copy from both languages", () => {
    for (const lang of ["en", "vi"] as const) {
      expect(Object.keys(translations[lang].changelog)).toEqual(["releases"]);
    }
  });

  it("lists every release with its date, title and items, newest first", () => {
    renderPage();
    const releases = translations.en.changelog.releases;
    const sections = Array.from(document.querySelectorAll("ul")).map((ul) => ul.parentElement as HTMLElement);
    releases.forEach((release, i) => {
      const section = within(sections[i]);
      expect(section.getByText(release.date)).toBeInTheDocument();
      expect(section.getByText(release.title)).toBeInTheDocument();
      expect(section.getAllByRole("listitem")).toHaveLength(release.items.length);
    });
    const dates = releases.map((r) => r.date);
    expect([...dates].sort().reverse()).toEqual(dates);
  });

  it("keeps the same entries in Vietnamese", async () => {
    renderPage();
    await userEvent.setup().click(screen.getByRole("button", { name: /vietnam|tiếng việt/i }));
    const vi = translations.vi.changelog.releases;
    expect(vi).toHaveLength(translations.en.changelog.releases.length);
    expect(screen.getByText(vi[0].title)).toBeInTheDocument();
    expect(screen.queryByText(/Nhật ký thật các thay đổi/)).not.toBeInTheDocument();
  });

  it("does not mention the old product name", () => {
    for (const lang of ["en", "vi"] as const) {
      expect(JSON.stringify(translations[lang].changelog)).not.toMatch(/omni ?flow/i);
    }
  });
});
