import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import HistoryPage from "./HistoryPage";
import { LanguageProvider } from "../i18n/LanguageContext";
import { loadHistory, recordDownload } from "../lib/history";

const renderPage = (onOpenUrl: (url: string) => void = vi.fn()) =>
  render(
    <LanguageProvider>
      <HistoryPage onNavigate={vi.fn()} onOpenUrl={onOpenUrl} />
    </LanguageProvider>
  );

const seed = (n: number) =>
  recordDownload({ url: `https://youtube.com/watch?v=${n}`, title: `Video ${n}`, platform: "YouTube", thumbnail: null });

beforeEach(() => {
  localStorage.clear();
});

describe("HistoryPage", () => {
  it("shows an empty state when nothing has been downloaded yet", () => {
    renderPage();
    expect(screen.getByText(/nothing here yet/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /clear history/i })).not.toBeInTheDocument();
  });

  it("lists downloads newest first with their links", () => {
    seed(1);
    seed(2);
    renderPage();
    const titles = screen.getAllByRole("heading", { level: 4 }).map((h) => h.textContent);
    expect(titles).toEqual(["Video 2", "Video 1"]);
    expect(screen.getByText("https://youtube.com/watch?v=2")).toBeInTheDocument();
  });

  it("hands the link back to Home when 'Download again' is pressed", async () => {
    seed(1);
    const onOpenUrl = vi.fn();
    const user = userEvent.setup();
    renderPage(onOpenUrl);

    await user.click(screen.getByRole("button", { name: /download again/i }));

    expect(onOpenUrl).toHaveBeenCalledWith("https://youtube.com/watch?v=1");
  });

  it("copies a link to the clipboard", async () => {
    seed(1);
    const user = userEvent.setup();
    renderPage();
    // userEvent.setup() installs its own clipboard stub; spy on it afterwards.
    const writeText = vi.spyOn(navigator.clipboard, "writeText").mockResolvedValue(undefined);

    await user.click(screen.getByRole("button", { name: /copy link/i }));

    expect(writeText).toHaveBeenCalledWith("https://youtube.com/watch?v=1");
  });

  it("removes a single entry", async () => {
    seed(1);
    seed(2);
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: /remove from history: video 2/i }));

    expect(screen.queryByText("Video 2")).not.toBeInTheDocument();
    expect(screen.getByText("Video 1")).toBeInTheDocument();
    expect(loadHistory().map((e) => e.title)).toEqual(["Video 1"]);
  });

  it("clears the whole history", async () => {
    seed(1);
    seed(2);
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: /clear history/i }));

    expect(screen.getByText(/nothing here yet/i)).toBeInTheDocument();
    expect(loadHistory()).toEqual([]);
  });

  it("only ever shows the 10 most recent downloads", () => {
    for (let n = 1; n <= 12; n += 1) seed(n);
    renderPage();
    const rows = screen.getAllByRole("heading", { level: 4 });
    expect(rows).toHaveLength(10);
    expect(within(rows[0].parentElement as HTMLElement).getByText("https://youtube.com/watch?v=12")).toBeInTheDocument();
  });
});
