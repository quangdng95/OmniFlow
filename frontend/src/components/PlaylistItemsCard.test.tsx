import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import PlaylistItemsCard from "./PlaylistItemsCard";
import { LanguageProvider } from "../i18n/LanguageContext";
import type { PlaylistItem } from "../types";

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
