import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import Footer from "./Footer";
import { LanguageProvider } from "../i18n/LanguageContext";

const renderFooter = (onNavigate = vi.fn()) => {
  render(
    <LanguageProvider>
      <Footer onNavigate={onNavigate} />
    </LanguageProvider>
  );
  return onNavigate;
};

describe("Footer", () => {
  it("is a contentinfo landmark with the byline", () => {
    renderFooter();
    expect(screen.getByRole("contentinfo")).toBeInTheDocument();
    expect(screen.getByText("By")).toBeInTheDocument();
    expect(screen.getByAltText("Logo")).toBeInTheDocument();
  });

  it("opens the Terms page from the footer link", async () => {
    const onNavigate = renderFooter();
    await userEvent.setup().click(screen.getByRole("button", { name: "Terms of Use" }));
    expect(onNavigate).toHaveBeenCalledWith("terms");
  });

  it("keeps the Terms link a 44px target", () => {
    renderFooter();
    expect(screen.getByRole("button", { name: "Terms of Use" }).className).toMatch(/min-h-11/);
  });
});
