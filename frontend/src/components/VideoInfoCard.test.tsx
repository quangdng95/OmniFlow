import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import VideoInfoCard from "./VideoInfoCard";
import { LanguageProvider } from "../i18n/LanguageContext";
import type { VideoInfo } from "../types";

vi.mock("../lib/saveFile", () => ({
  preparePlainFile: vi.fn(() => Promise.resolve({ files: [], fallbackBlob: new Blob(), fallbackFilename: "x" })),
  prepareZipFiles: vi.fn(),
  sharePreparedSave: vi.fn().mockResolvedValue("shared"),
  isNotAllowedError: () => false,
}));

const INFO: VideoInfo = {
  type: "video",
  title: "Paper boat",
  uploader: "Origami Lab",
  thumbnail: "https://img/x.jpg",
  platform: "YouTube",
  qualities: ["Best"],
  duration: "02:47",
};

const setup = (props: Partial<React.ComponentProps<typeof VideoInfoCard>> = {}) => {
  const h = { onDownload: vi.fn(), onCancel: vi.fn(), onOpenFolder: vi.fn() };
  const view = render(
    <LanguageProvider>
      <VideoInfoCard info={INFO} actionState="idle" percent={0} filename={null} {...h} {...props} />
    </LanguageProvider>
  );
  return { ...h, ...view };
};

const section = () => screen.getByText("Paper boat").closest("section") as HTMLElement;

describe("VideoInfoCard", () => {
  it("shows the elapsed counter only while processing (100%), and drops it on cancel", () => {
    const { rerender } = setup({ actionState: "downloading", percent: 50 });
    expect(screen.queryByRole("timer")).not.toBeInTheDocument();
    const props = { info: INFO, percent: 100, filename: null, onDownload: vi.fn(), onCancel: vi.fn() };
    rerender(
      <LanguageProvider>
        <VideoInfoCard {...props} actionState="downloading" />
      </LanguageProvider>
    );
    expect(screen.getByText(/Processing video/)).toBeInTheDocument();
    expect(screen.getByRole("timer")).toHaveTextContent("0:00");
    rerender(
      <LanguageProvider>
        <VideoInfoCard {...props} actionState="idle" />
      </LanguageProvider>
    );
    expect(screen.queryByRole("timer")).not.toBeInTheDocument();
  });

  it("rounds a fractional percent once, so the big number and the status line agree", () => {
    setup({ actionState: "downloading", percent: 0.7814356263219739 });
    expect(screen.getByText("1%")).toBeInTheDocument();
    expect(screen.getByText("1% Downloading…")).toBeInTheDocument();
    expect(screen.queryByText(/0\.78/)).not.toBeInTheDocument();
  });

  it("shows title, uploader · duration, the platform tag and the thumbnail", () => {
    setup();
    expect(screen.getByRole("heading", { name: "Paper boat" })).toBeInTheDocument();
    expect(screen.getByText("Origami Lab · 02:47")).toBeInTheDocument();
    expect(screen.getByText("YouTube")).toBeInTheDocument();
    expect(screen.getByAltText("Paper boat")).toHaveAttribute("src", "https://img/x.jpg");
  });

  it("works without a thumbnail", () => {
    setup({ info: { ...INFO, thumbnail: null } });
    expect(screen.queryByAltText("Paper boat")).not.toBeInTheDocument();
    expect(screen.getByText("YouTube")).toBeInTheDocument();
  });

  it("idle: Start Download is the one action, in the platform colour", async () => {
    const { onDownload } = setup();
    expect(section().className).toContain("bg-platform-youtube");
    await userEvent.setup().click(screen.getByRole("button", { name: "Start Download" }));
    expect(onDownload).toHaveBeenCalledTimes(1);
  });

  it("downloading: shows the percentage, a progress bar and Cancel", async () => {
    const { onCancel } = setup({ actionState: "downloading", percent: 64 });
    expect(screen.getByText("64% Downloading…")).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Start Download" })).not.toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: /Cancel/ }));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("downloading at 100%: says it is finalizing", () => {
    setup({ actionState: "downloading", percent: 100 });
    expect(screen.getByText(/Finalizing|Processing/i)).toBeInTheDocument();
  });

  it("done: block turns lime, shows the file and offers Open Folder + Download again", async () => {
    const { onOpenFolder, onDownload } = setup({ actionState: "done", filename: "boat.mp4" });
    expect(section().className).toContain("bg-lime");
    expect(screen.getByText("boat.mp4")).toBeInTheDocument();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Open Folder" }));
    await user.click(screen.getByRole("button", { name: /download again/i }));
    expect(onOpenFolder).toHaveBeenCalledTimes(1);
    expect(onDownload).toHaveBeenCalledTimes(1);
  });

  it("done on a remote deployment: offers Save to device instead of Open Folder", () => {
    setup({ actionState: "done", filename: "boat.mp4", onOpenFolder: undefined, downloadUrl: "/api/download-file/j1" });
    expect(screen.getByRole("button", { name: "Save to device" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Open Folder" })).not.toBeInTheDocument();
  });

  it("fail: block turns ink, says Failed and offers Retry", async () => {
    const { onDownload } = setup({ actionState: "fail" });
    expect(section().className).toContain("bg-ink");
    expect(screen.getByRole("alert")).toHaveTextContent("Failed");
    await userEvent.setup().click(screen.getByRole("button", { name: "Retry" }));
    expect(onDownload).toHaveBeenCalledTimes(1);
  });

  it("phone auto-save: no Start button, progress while the job runs", () => {
    setup({ autoSave: true, actionState: "idle", percent: 10 });
    expect(screen.queryByRole("button", { name: "Start Download" })).not.toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toBeInTheDocument();
  });
});

describe("VideoInfoCard conversion progress", () => {
  it("shows the real percent while the video is converted", () => {
    setup({ actionState: "downloading", percent: 100, encodePercent: 42 });
    expect(screen.getByText(/Converting to H\.264… 42%/)).toBeInTheDocument();
  });

  it("falls back to the generic processing line when there is no conversion percent", () => {
    setup({ actionState: "downloading", percent: 100, encodePercent: null });
    expect(screen.getByText(/Processing video…/)).toBeInTheDocument();
  });
});
