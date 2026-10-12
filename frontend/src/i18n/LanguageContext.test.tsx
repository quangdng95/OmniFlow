import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { LanguageProvider, useLanguage } from "./LanguageContext";
import LanguageSwitcher from "../components/LanguageSwitcher";

const Tagline = () => {
  const { t } = useLanguage();
  return <p>{t.header.home.taglineLines.join(" ")}</p>;
};

describe("LanguageProvider", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.lang = "";
  });

  it("defaults to English and marks the document language", () => {
    render(
      <LanguageProvider>
        <Tagline />
      </LanguageProvider>
    );
    expect(screen.getByText("Paste a link. Get the file.")).toBeInTheDocument();
    expect(document.documentElement.lang).toBe("en");
  });

  it("switching to Vietnamese changes the copy and <html lang> (which the :lang(vi) CSS depends on)", async () => {
    const user = userEvent.setup();
    render(
      <LanguageProvider>
        <LanguageSwitcher />
        <Tagline />
      </LanguageProvider>
    );
    await user.click(screen.getByRole("button", { name: /vietnam|tiếng việt/i }));
    expect(screen.getByText("Dán link. Nhận file.")).toBeInTheDocument();
    expect(document.documentElement.lang).toBe("vi");

    await user.click(screen.getByRole("button", { name: /english/i }));
    expect(document.documentElement.lang).toBe("en");
  });

  it("remembers the choice for the next visit", async () => {
    const user = userEvent.setup();
    const { unmount } = render(
      <LanguageProvider>
        <LanguageSwitcher />
      </LanguageProvider>
    );
    await user.click(screen.getByRole("button", { name: /vietnam|tiếng việt/i }));
    unmount();
    render(
      <LanguageProvider>
        <Tagline />
      </LanguageProvider>
    );
    expect(screen.getByText("Dán link. Nhận file.")).toBeInTheDocument();
  });
});
