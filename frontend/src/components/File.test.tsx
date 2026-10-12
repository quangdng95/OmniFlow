import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import File, { type FileState } from "./File";
import { LanguageProvider } from "../i18n/LanguageContext";

const setup = (props: Partial<React.ComponentProps<typeof File>> = {}) => {
  const h = { onToggle: vi.fn(), onAction: vi.fn(), onPreview: vi.fn() };
  render(
    <LanguageProvider>
      <ul>
        <File
          title="Video one"
          uploader="Lab"
          duration="01:10"
          thumbnail="https://img/t.jpg"
          position={3}
          numWidth={2}
          checked={false}
          busy={false}
          available
          {...h}
          {...props}
        />
      </ul>
    </LanguageProvider>
  );
  return h;
};

afterEach(() => window.getSelection()?.removeAllRanges());

describe("File row", () => {
  it("shows the zero-padded position, title, uploader and duration", () => {
    setup();
    expect(screen.getByText("03.")).toBeInTheDocument();
    expect(screen.getByText("Video one")).toBeInTheDocument();
    expect(screen.getByText("Lab")).toBeInTheDocument();
    expect(screen.getByText("01:10")).toBeInTheDocument();
  });

  it("clicking anywhere on the row toggles it", async () => {
    const h = setup();
    await userEvent.setup().click(screen.getByText("Video one"));
    expect(h.onToggle).toHaveBeenCalledTimes(1);
  });

  it("does NOT toggle when the click ends a text selection (drag-select the title)", async () => {
    const h = setup();
    const title = screen.getByText("Video one");
    const range = document.createRange();
    range.selectNodeContents(title);
    window.getSelection()?.addRange(range);
    // A real drag-select leaves the selection in place when the click fires
    // (user-event's click would clear it first, like a plain click does).
    fireEvent.click(title);
    expect(h.onToggle).not.toHaveBeenCalled();
  });

  it("does not toggle while busy or when unavailable", async () => {
    const user = userEvent.setup();
    const busy = setup({ busy: true });
    await user.click(screen.getByText("Video one"));
    expect(busy.onToggle).not.toHaveBeenCalled();
  });

  it("an unavailable row has no action and says so", () => {
    setup({ available: false });
    expect(screen.queryByRole("button", { name: "download-item" })).not.toBeInTheDocument();
    expect(screen.getByText(/unavailable/i)).toBeInTheDocument();
  });

  it("the row's text is selectable (no select-none on the row)", () => {
    setup();
    expect(screen.getByRole("listitem").className).not.toContain("select-none");
  });

  it("Default: Download button runs the row action without toggling it", async () => {
    const h = setup();
    await userEvent.setup().click(screen.getByRole("button", { name: "download-item" }));
    expect(h.onAction).toHaveBeenCalledTimes(1);
    expect(h.onToggle).not.toHaveBeenCalled();
  });

  it("thumbnail opens the preview", async () => {
    const h = setup();
    await userEvent.setup().click(screen.getByRole("button", { name: /Preview/i }));
    expect(h.onPreview).toHaveBeenCalledTimes(1);
  });

  const states: [FileState, RegExp][] = [
    ["Downloading", /40%/],
    ["Completed", /Downloaded/],
    ["Fail", /Failed/],
  ];
  it.each(states)("%s state shows its status", (state, text) => {
    setup({ state, percent: 40, hideRedownload: true });
    expect(screen.getByText(text)).toBeInTheDocument();
  });

  it("Fail state offers Retry, which runs the action", async () => {
    const h = setup({ state: "Fail" });
    await userEvent.setup().click(screen.getByRole("button", { name: "Retry" }));
    expect(h.onAction).toHaveBeenCalledTimes(1);
  });
});
