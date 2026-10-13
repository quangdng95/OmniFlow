import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { usePreparedSave } from "./usePreparedSave";
import { LanguageProvider } from "../i18n/LanguageContext";
import type { PrepareOptions, PreparedSave } from "../lib/saveFile";
import * as saveFile from "../lib/saveFile";

vi.mock("sonner", () => ({ toast: { success: vi.fn(), info: vi.fn(), error: vi.fn() }, Toaster: () => null }));
vi.mock("../lib/saveFile", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/saveFile")>();
  return { ...actual, getSavePlatform: vi.fn(() => "ios"), sharePreparedSave: vi.fn() };
});

import { toast } from "sonner";

const videoFile = new File(["x"], "clip.mp4", { type: "video/mp4" });
const audioFile = new File(["x"], "song.mp3", { type: "audio/mpeg" });

interface HarnessProps {
  prepare: (url: string, options: PrepareOptions) => Promise<PreparedSave>;
  url?: string;
}

const Harness = ({ prepare, url = "/api/download-file/j1" }: HarnessProps) => {
  const { preparing, progress, shareKind, saving, failed, save } = usePreparedSave(url, prepare);
  const label = preparing
    ? `preparing ${progress ?? "?"}`
    : failed
      ? "failed"
      : shareKind === "photos"
        ? "save to photos"
        : shareKind === "files"
          ? "save to files"
          : "save to device";
  return (
    <button type="button" disabled={saving || preparing} onClick={() => void save()}>
      {label}
    </button>
  );
};

const renderHarness = (props: HarnessProps) =>
  render(
    <LanguageProvider>
      <Harness {...props} />
    </LanguageProvider>
  );

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(saveFile.getSavePlatform).mockReturnValue("ios");
});

describe("usePreparedSave on iOS", () => {
  it("goes Preparing N% (disabled) -> Save to Photos, and the tap shares exactly once", async () => {
    let finish!: (p: PreparedSave) => void;
    let report!: (n: number) => void;
    const prepare = vi.fn((_url: string, options: PrepareOptions) => {
      report = options.onProgress as (n: number) => void;
      return new Promise<PreparedSave>((resolve) => {
        finish = resolve;
      });
    });
    vi.mocked(saveFile.sharePreparedSave).mockResolvedValue("shared");
    renderHarness({ prepare });

    const button = await screen.findByRole("button");
    expect(button).toHaveTextContent("preparing ?");
    expect(button).toBeDisabled();
    act(() => report(42));
    expect(button).toHaveTextContent("preparing 42");

    await act(async () => finish({ files: [videoFile], fallbackFilename: "clip.mp4" }));
    await waitFor(() => expect(button).toHaveTextContent("save to photos"));
    expect(button).toBeEnabled();

    await userEvent.click(button);
    expect(saveFile.sharePreparedSave).toHaveBeenCalledTimes(1);
    expect(toast.success).toHaveBeenCalledWith("Saved to your device"); // confirmed on the page after the share sheet
  });

  it("offers Save to Files (not Photos) for audio", async () => {
    renderHarness({ prepare: () => Promise.resolve({ files: [audioFile], fallbackFilename: "song.mp3" }) });
    await waitFor(() => expect(screen.getByRole("button")).toHaveTextContent("save to files"));
  });

  it("a file that has to be streamed stays a plain Save to device and the tap explains where it went", async () => {
    vi.mocked(saveFile.sharePreparedSave).mockResolvedValue("downloaded");
    renderHarness({
      prepare: () => Promise.resolve({ files: [], fallbackFilename: "big.mp4", directUrl: "/api/download-file/j1", reason: "too-big" }),
    });
    const button = screen.getByRole("button");
    await waitFor(() => expect(button).toHaveTextContent("save to device"));
    await userEvent.click(button);
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith(expect.stringMatching(/Files app/)));
    expect(toast.success).not.toHaveBeenCalledWith(expect.stringMatching(/download bar/i));
  });

  it("backing out of the share sheet is silent and leaves the button usable", async () => {
    vi.mocked(saveFile.sharePreparedSave).mockRejectedValue(Object.assign(new Error("cancel"), { name: "AbortError" }));
    renderHarness({ prepare: () => Promise.resolve({ files: [videoFile], fallbackFilename: "clip.mp4" }) });
    const button = screen.getByRole("button");
    await waitFor(() => expect(button).toHaveTextContent("save to photos"));
    await userEvent.click(button);
    await waitFor(() => expect(saveFile.sharePreparedSave).toHaveBeenCalledTimes(1));
    expect(toast.error).not.toHaveBeenCalled();
    expect(toast.info).not.toHaveBeenCalled();
    expect(button).toBeEnabled();
  });

  it("aborts the fetch when the video changes or the page closes, and never ends stuck on Preparing", async () => {
    let signal: AbortSignal | undefined;
    const prepare = vi.fn((_url: string, options: PrepareOptions) => {
      signal = options.signal;
      return new Promise<PreparedSave>(() => {});
    });
    const view = renderHarness({ prepare });
    await waitFor(() => expect(signal).toBeDefined());
    expect(signal?.aborted).toBe(false);
    view.unmount();
    expect(signal?.aborted).toBe(true);
  });

  it("a failed preparation ends in 'failed', not Preparing forever", async () => {
    renderHarness({ prepare: () => Promise.reject(new Error("Failed to fetch file (500)")) });
    await waitFor(() => expect(screen.getByRole("button")).toHaveTextContent("failed"));
    expect(screen.getByRole("button")).toBeEnabled();
  });
});

describe("usePreparedSave elsewhere", () => {
  it("Android: no preparing state; the tap streams the file and points at notifications/Downloads", async () => {
    vi.mocked(saveFile.getSavePlatform).mockReturnValue("android");
    vi.mocked(saveFile.sharePreparedSave).mockResolvedValue("downloaded");
    renderHarness({
      prepare: () => Promise.resolve({ files: [], fallbackFilename: "x.mp4", directUrl: "/api/download-file/j1", reason: "not-ios" }),
    });
    const button = screen.getByRole("button");
    expect(button).not.toHaveTextContent("preparing");
    await waitFor(() => expect(button).toHaveTextContent("save to device"));
    await userEvent.click(button);
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith(expect.stringMatching(/notifications or the Downloads folder/)));
  });
});
