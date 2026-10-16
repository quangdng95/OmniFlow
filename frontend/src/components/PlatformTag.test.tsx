import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import PlatformTag from "./PlatformTag";
import type { Platform } from "../types";

describe("PlatformTag", () => {
  it.each(["YouTube", "TikTok", "Instagram", "Facebook", "RedNote", "LinkedIn", "Threads", "Pinterest", "X", "Link"] as Platform[])(
    "shows %s as text (readable, selectable, not an image)",
    (platform) => {
      render(<PlatformTag platform={platform} />);
      expect(screen.getByText(platform)).toBeInTheDocument();
      expect(screen.queryByRole("img")).not.toBeInTheDocument();
    }
  );

  it("takes its colour from the surrounding block", () => {
    render(<PlatformTag platform="YouTube" />);
    expect(screen.getByText("YouTube").className).toContain("border-current");
  });
});
