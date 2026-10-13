import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import UrlInputCard, { type UrlInputStatus } from "./UrlInputCard";
import { LanguageProvider } from "../i18n/LanguageContext";

const setup = (props: Partial<React.ComponentProps<typeof UrlInputCard>> = {}) => {
  const handlers = { onChange: vi.fn(), onPaste: vi.fn(), onClear: vi.fn(), onQualityChange: vi.fn() };
  render(
    <LanguageProvider>
      <UrlInputCard value="" status={"idle" as UrlInputStatus} {...handlers} {...props} />
    </LanguageProvider>
  );
  return handlers;
};

describe("UrlInputCard slow-processing hint", () => {
  const Q = ["2160p", "1440p", "1080p", "360p", "Best", "Audio Only"];
  const HINT = /can take longer to process/i;

  it.each(["2160p", "1440p"])("shows the hint when %s is selected", (q) => {
    setup({ qualities: Q, qualityValue: q });
    expect(screen.getByText(HINT)).toBeInTheDocument();
  });

  it.each(["1080p", "360p", "Best", "Audio Only"])("hides the hint for %s", (q) => {
    setup({ qualities: Q, qualityValue: q });
    expect(screen.queryByText(HINT)).not.toBeInTheDocument();
  });

  it("hides the hint when there is no quality picker", () => {
    setup({ qualities: ["2160p"], qualityValue: "2160p" });
    expect(screen.queryByText(HINT)).not.toBeInTheDocument();
  });
});

describe("UrlInputCard", () => {
  it("has a visible label tied to the field", () => {
    setup();
    expect(screen.getByLabelText("Video link")).toBe(screen.getByPlaceholderText("Copy and Paste your url"));
  });

  it("asks the browser for a URL keyboard and turns off autocorrect", () => {
    setup();
    const input = screen.getByLabelText("Video link");
    expect(input).toHaveAttribute("type", "url");
    expect(input).toHaveAttribute("inputmode", "url");
    expect(input).toHaveAttribute("autocapitalize", "off");
  });

  it("empty: the action is Paste", async () => {
    const h = setup();
    await userEvent.setup().click(screen.getByRole("button", { name: "Paste" }));
    expect(h.onPaste).toHaveBeenCalledTimes(1);
  });

  it("while pasting the button is disabled and says so", () => {
    setup({ pasting: true });
    expect(screen.getByRole("button", { name: "Pasting…" })).toBeDisabled();
  });

  it("filled: the action is Remove URL and calls onClear", async () => {
    const h = setup({ value: "https://youtube.com/x", status: "result" });
    expect(screen.queryByRole("button", { name: "Paste" })).not.toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: /URL/ }));
    expect(h.onClear).toHaveBeenCalledTimes(1);
  });

  it("can disable Clear while a download runs", () => {
    setup({ value: "https://youtube.com/x", clearDisabled: true });
    expect(screen.getByRole("button", { name: /URL/ })).toBeDisabled();
  });

  it("checking: shows a status, locks the field and drops the buttons", () => {
    setup({ value: "https://youtube.com/x", status: "checking" });
    expect(screen.getByRole("status")).toHaveTextContent("Checking");
    expect(screen.getByLabelText("Video link")).toBeDisabled();
    expect(screen.queryByRole("button", { name: /URL|Paste/ })).not.toBeInTheDocument();
  });

  it("error: marks the field invalid", () => {
    setup({ value: "x", status: "error" });
    expect(screen.getByLabelText("Video link")).toHaveAttribute("aria-invalid", "true");
  });

  it("reports typing", async () => {
    const h = setup();
    await userEvent.setup().type(screen.getByLabelText("Video link"), "a");
    expect(h.onChange).toHaveBeenCalledWith("a");
  });

  it("shows the quality picker only when there is a choice, and reports a change", async () => {
    const h = setup({ value: "u", status: "result", qualities: ["Best", "720p"], qualityValue: "Best" });
    await userEvent.setup().click(screen.getByRole("tab", { name: "720p" }));
    expect(h.onQualityChange).toHaveBeenCalledWith("720p");
  });

  it("hides the quality picker for a single option", () => {
    setup({ value: "u", status: "result", qualities: ["Image"], qualityValue: "Image" });
    expect(screen.queryByRole("tab")).not.toBeInTheDocument();
  });
});
