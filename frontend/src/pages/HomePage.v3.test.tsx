import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import HomePage from "./HomePage";
import { api } from "../api";
import { LanguageProvider } from "../i18n/LanguageContext";
import LanguageSwitcher from "../components/LanguageSwitcher";
import type { VideoInfo } from "../types";

vi.mock("../api", () => ({
  api: {
    getSettings: vi.fn(),
    checkLink: vi.fn(),
    startDownload: vi.fn(),
    startBatchDownload: vi.fn(),
    getProgress: vi.fn(),
    cancelJob: vi.fn(),
    openFolder: vi.fn(),
    getClipboard: vi.fn(),
  },
}));
vi.mock("../lib/saveFile", () => ({
  preparePlainFile: vi.fn(() => Promise.resolve({ files: [], fallbackBlob: new Blob(), fallbackFilename: "x" })),
  prepareZipFiles: vi.fn(),
  sharePreparedSave: vi.fn().mockResolvedValue("shared"),
  isNotAllowedError: () => false,
}));

const mockedApi = vi.mocked(api, true);

const VIDEO: VideoInfo = {
  type: "video",
  title: "Paper boat",
  uploader: "Lab",
  thumbnail: null,
  platform: "TikTok",
  qualities: ["Best", "720p"],
  duration: "00:30",
};

const renderHome = () =>
  render(
    <LanguageProvider>
      <LanguageSwitcher />
      <HomePage onNavigate={vi.fn()} />
    </LanguageProvider>
  );

describe("HomePage (V3)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    mockedApi.getClipboard.mockRejectedValue(new Error("no clipboard"));
    mockedApi.cancelJob.mockResolvedValue({ ok: true });
  });

  describe("empty state", () => {
    it("hero is a two-line h1 plus a one-line promise", () => {
      renderHome();
      const h1 = screen.getByRole("heading", { level: 1 });
      expect(within(h1).getByText("Paste a link.")).toBeInTheDocument();
      expect(within(h1).getByText("Get the file.")).toBeInTheDocument();
      expect(screen.getByText("Free, no sign-up. Up to 1080p, or audio only.")).toBeInTheDocument();
    });

    it("the two hero lines are fixed blocks, so the break never depends on the screen width", () => {
      renderHome();
      const lines = Array.from(screen.getByRole("heading", { level: 1 }).querySelectorAll("span"));
      expect(lines).toHaveLength(2);
      for (const line of lines) expect(line.className).toContain("block");
    });

    it("Vietnamese hero keeps the same two-line structure", async () => {
      renderHome();
      await userEvent.setup().click(screen.getByRole("button", { name: /vietnam|tiếng việt/i }));
      const h1 = screen.getByRole("heading", { level: 1 });
      expect(within(h1).getByText("Dán link.")).toBeInTheDocument();
      expect(within(h1).getByText("Nhận file.")).toBeInTheDocument();
      expect(h1.querySelectorAll("span")).toHaveLength(2);
    });

    it("lists all eight platforms as coloured tiles", () => {
      renderHome();
      for (const name of ["YouTube", "TikTok", "Instagram", "Facebook", "Threads", "X", "LinkedIn", "RedNote"]) {
        const tile = screen.getByText(name, { selector: "li" });
        expect(tile.className).toMatch(/bg-platform-/);
      }
    });

    it("has the three accordion sections, collapsed", () => {
      renderHome();
      for (const name of ["How it works", "Why Vidrop", "Questions"]) {
        expect(screen.getByRole("button", { name })).toHaveAttribute("aria-expanded", "false");
      }
    });

    it("expanding Questions reveals all four FAQ entries", async () => {
      renderHome();
      await userEvent.setup().click(screen.getByRole("button", { name: "Questions" }));
      for (const q of ["Where are my files saved?", "Is it really free?", "Can I download a whole playlist?", "Why did my link fail?"]) {
        expect(await screen.findByText(q)).toBeInTheDocument();
      }
    });

    it("expanding How it works shows the three steps", async () => {
      renderHome();
      await userEvent.setup().click(screen.getByRole("button", { name: "How it works" }));
      expect(await screen.findByText("Copy the link of a video, photo or playlist.")).toBeInTheDocument();
      expect(screen.getByText(/Select Start Download/)).toBeInTheDocument();
    });
  });

  describe("result and error states", () => {
    it("a result swaps the page content for the platform block and hides the intro sections", async () => {
      mockedApi.checkLink.mockResolvedValue(VIDEO);
      renderHome();
      await userEvent.setup({ delay: null }).type(screen.getByLabelText("Video link"), "https://tiktok.com/a");
      expect(await screen.findByRole("heading", { name: "Paper boat" }, { timeout: 3000 })).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Questions" })).not.toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Start Download" })).toBeInTheDocument();
    });

    it("a failed check shows an alert block with the message, hint and Retry - and no toast needed", async () => {
      mockedApi.checkLink.mockRejectedValue(new Error("This site isn't supported yet."));
      renderHome();
      await userEvent.setup({ delay: null }).type(screen.getByLabelText("Video link"), "https://example.com/x");
      const alert = await screen.findByRole("alert", undefined, { timeout: 3000 });
      expect(alert).toHaveTextContent("Couldn't check this link");
      expect(alert).toHaveTextContent("This site isn't supported yet.");
      expect(within(alert).getByRole("button", { name: "Retry" })).toBeInTheDocument();
      expect(screen.getByLabelText("Video link")).toHaveAttribute("aria-invalid", "true");
    });

    it("Retry checks the same link again", async () => {
      mockedApi.checkLink.mockRejectedValueOnce(new Error("Network down")).mockResolvedValueOnce(VIDEO);
      renderHome();
      const user = userEvent.setup({ delay: null });
      await user.type(screen.getByLabelText("Video link"), "https://tiktok.com/a");
      await user.click(await screen.findByRole("button", { name: "Retry" }, { timeout: 3000 }));
      await waitFor(() => expect(mockedApi.checkLink).toHaveBeenCalledTimes(2));
      expect(await screen.findByRole("heading", { name: "Paper boat" })).toBeInTheDocument();
      expect(screen.queryByText("Couldn't check this link")).not.toBeInTheDocument();
    });

    it("editing the link clears the error block", async () => {
      mockedApi.checkLink.mockRejectedValue(new Error("Bad link"));
      renderHome();
      const user = userEvent.setup({ delay: null });
      await user.type(screen.getByLabelText("Video link"), "https://example.com/x");
      await screen.findByRole("alert", undefined, { timeout: 3000 });
      await user.click(screen.getByRole("button", { name: "Clear URL" }));
      await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
    });
  });

  describe("text selection", () => {
    it("no text container on the home page blocks selection - only controls opt out", () => {
      const { container } = renderHome();
      const blockers = Array.from(container.querySelectorAll<HTMLElement>("[class*='select-none']"));
      // The shadcn Label primitive carries select-none; index.css overrides it
      // for [data-slot=label] ("Video link" must be selectable), so it is exempt here.
      const nonControls = blockers.filter(
        (el) => !el.closest("button, [role=group]") && el.tagName !== "BUTTON" && el.dataset.slot !== "label"
      );
      expect(nonControls.map((el) => el.tagName + "." + el.className)).toEqual([]);
    });

    it.each(["h1", "h1 + p"])("%s is selectable", (selector) => {
      const { container } = renderHome();
      const el = container.querySelector(selector) as HTMLElement;
      expect(el).not.toBeNull();
      expect(el.closest("[class*='select-none']")).toBeNull();
    });
  });
});
