import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { RowProgress } from "../types";
import PlaylistItemsCard from "./PlaylistItemsCard";
import { LanguageProvider } from "../i18n/LanguageContext";
import type { PlaylistItem } from "../types";

vi.mock("../lib/saveFile", () => ({
  prepareZipFiles: vi.fn(() => Promise.resolve({ files: [], fallbackBlob: new Blob(), fallbackFilename: "x" })),
  sharePreparedSave: vi.fn().mockResolvedValue("shared"),
  isNotAllowedError: () => false,
}));

const makeItem = (n: number): PlaylistItem =>
  ({
    title: `Slide ${n}`,
    thumbnail: `https://cdn.example/slide-${n}.jpg`,
    position: n,
    kind: "image",
    entry_index: n,
  }) as PlaylistItem;

const renderCard = (items: PlaylistItem[]) =>
  render(
    <LanguageProvider>
      <PlaylistItemsCard
        title="Carousel"
        platform="TikTok"
        items={items}
        busy={false}
        rowStatus={{}}
        batchSummary={null}
        quality="Best"
        onDownloadItems={vi.fn()}
      />
    </LanguageProvider>
  );

describe("PlaylistItemsCard thumbnail preview", () => {
  it("enlarges a row's thumbnail without selecting the row, and steps through items in order", async () => {
    const user = userEvent.setup();
    renderCard([makeItem(1), makeItem(2), makeItem(3)]);

    await user.click(screen.getByRole("button", { name: "Preview Slide 2" }));

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("02. Slide 2")).toBeInTheDocument();
    expect(screen.getByText("2 / 3")).toBeInTheDocument();
    // Opening the preview must not tick the row's checkbox.
    expect(screen.queryByText(/Download Items Selected/i)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Next item" }));
    expect(screen.getByText("03. Slide 3")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next item" })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Previous item" }));
    await user.click(screen.getByRole("button", { name: "Previous item" }));
    expect(screen.getByText("01. Slide 1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous item" })).toBeDisabled();
  });
});

const allDone = (count: number): Record<number, RowProgress> =>
  Object.fromEntries(Array.from({ length: count }, (_, i) => [i, { status: "done", percent: 100 }]));

describe("PlaylistItemsCard after a finished batch", () => {
  it("keeps downloaded rows selectable so several can be downloaded again at once", async () => {
    const onDownloadItems = vi.fn();
    const user = userEvent.setup();
    render(
      <LanguageProvider>
        <PlaylistItemsCard
          title="Carousel"
          platform="Instagram"
          items={[makeItem(1), makeItem(2), makeItem(3)]}
          busy={false}
          rowStatus={allDone(3)}
          batchSummary={null}
          quality="Best"
          onDownloadItems={onDownloadItems}
        />
      </LanguageProvider>
    );

    const selectAll = screen.getByRole("checkbox", { name: "Select all" });
    expect(selectAll).not.toHaveAttribute("aria-disabled", "true");
    await user.click(selectAll);
    await user.click(screen.getByRole("button", { name: /Download Items Selected/i }));

    expect(onDownloadItems).toHaveBeenCalledWith([0, 1, 2], "Best");
  });

  it("keeps Download All usable once every row is saved", async () => {
    const onDownloadItems = vi.fn();
    const user = userEvent.setup();
    render(
      <LanguageProvider>
        <PlaylistItemsCard
          title="Carousel"
          platform="Instagram"
          items={[makeItem(1), makeItem(2)]}
          busy={false}
          rowStatus={allDone(2)}
          batchSummary={null}
          quality="Best"
          onDownloadItems={onDownloadItems}
        />
      </LanguageProvider>
    );

    await user.click(screen.getByRole("button", { name: "Download All" }));
    expect(onDownloadItems).toHaveBeenCalledWith([0, 1], "Best");
  });

  it("offers the save-to-device button at the top as well as the bottom", () => {
    render(
      <LanguageProvider>
        <PlaylistItemsCard
          title="Carousel"
          platform="Instagram"
          items={[makeItem(1), makeItem(2)]}
          busy={false}
          rowStatus={allDone(2)}
          batchSummary={null}
          quality="Best"
          onDownloadItems={vi.fn()}
          downloadUrl="/api/download-file/job-1"
        />
      </LanguageProvider>
    );

    expect(screen.getAllByRole("button", { name: "Save to device" })).toHaveLength(2);
  });
});

describe("PlaylistItemsCard row selection", () => {
  const renderRows = () =>
    render(
      <LanguageProvider>
        <PlaylistItemsCard
          title="Carousel"
          platform="Instagram"
          items={[makeItem(1), makeItem(2)]}
          busy={false}
          rowStatus={allDone(2)}
          batchSummary={null}
          quality="Best"
          onDownloadItems={vi.fn()}
        />
      </LanguageProvider>
    );

  it("selects a row by clicking its checkbox", async () => {
    const user = userEvent.setup();
    renderRows();
    const [, rowBox] = screen.getAllByRole("checkbox");
    await user.click(rowBox);
    expect(rowBox).toHaveAttribute("aria-checked", "true");
    await user.click(rowBox);
    expect(rowBox).toHaveAttribute("aria-checked", "false");
  });

  it("selects a row by clicking anywhere on the card, without opening the thumbnail preview", async () => {
    const user = userEvent.setup();
    renderRows();
    await user.click(screen.getByText("Slide 1"));
    expect(screen.getAllByRole("checkbox")[1]).toHaveAttribute("aria-checked", "true");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("keeps the thumbnail preview separate: it opens the preview and does not select the row", async () => {
    const user = userEvent.setup();
    renderRows();
    // Grab the box first: an open dialog aria-hides the rest of the page.
    const [, rowBox] = screen.getAllByRole("checkbox");
    await user.click(screen.getByRole("button", { name: "Preview Slide 1" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(rowBox).toHaveAttribute("aria-checked", "false");
  });
});
