import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import LanguageSwitcher from "./LanguageSwitcher";
import { LanguageProvider, useLanguage } from "../i18n/LanguageContext";

const CurrentLabel = () => {
  const { t } = useLanguage();
  return <p data-testid="home-label">{t.header.nav.home}</p>;
};

const renderSwitcher = () =>
  render(
    <LanguageProvider>
      <LanguageSwitcher />
      <CurrentLabel />
    </LanguageProvider>
  );

describe("LanguageSwitcher", () => {
  beforeEach(() => {
    localStorage.clear();
    document.cookie = "omniflow-language=; path=/; max-age=0";
  });

  it("offers English and Vietnamese and marks the active one", () => {
    renderSwitcher();
    expect(screen.getByRole("group", { name: "Language" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "English" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Tiếng Việt" })).toHaveAttribute("aria-pressed", "false");
  });

  it("switches the whole UI to Vietnamese in one click, and back", async () => {
    const user = userEvent.setup();
    renderSwitcher();
    expect(screen.getByTestId("home-label")).toHaveTextContent("Home");

    await user.click(screen.getByRole("button", { name: "Tiếng Việt" }));
    expect(screen.getByTestId("home-label")).toHaveTextContent("Trang chủ");
    expect(screen.getByRole("button", { name: "Tiếng Việt" })).toHaveAttribute("aria-pressed", "true");
    // The group's own label follows the language too.
    expect(screen.getByRole("group", { name: "Ngôn ngữ" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "English" }));
    expect(screen.getByTestId("home-label")).toHaveTextContent("Home");
  });

  it("remembers the choice across a reload", async () => {
    const user = userEvent.setup();
    const first = renderSwitcher();
    await user.click(screen.getByRole("button", { name: "Tiếng Việt" }));
    first.unmount();

    renderSwitcher();
    expect(screen.getByTestId("home-label")).toHaveTextContent("Trang chủ");
  });
});
