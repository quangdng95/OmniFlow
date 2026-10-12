import { describe, expect, it } from "vitest";
import { blockToneClass } from "./platform";
import type { Platform } from "../types";

const PLATFORMS: Platform[] = ["YouTube", "Instagram", "TikTok", "Facebook", "RedNote", "LinkedIn", "Threads", "X", "Link"];

describe("blockToneClass", () => {
  it.each(PLATFORMS)("gives %s its own block colour with white text", (platform) => {
    const cls = blockToneClass(platform);
    expect(cls).toMatch(/bg-platform-/);
    expect(cls).toContain("text-on-ink");
    expect(cls).toContain("--block-bg");
  });

  it("uses a different colour token per branded platform", () => {
    const branded: Platform[] = ["YouTube", "Instagram", "Facebook", "RedNote", "LinkedIn"];
    const tokens = branded.map((p) => /bg-platform-\w+/.exec(blockToneClass(p))?.[0]);
    expect(new Set(tokens).size).toBe(branded.length);
  });

  it("flips the hard shadow to white on the dark platforms so it stays visible", () => {
    for (const p of ["TikTok", "Threads", "X", "Link"] as Platform[]) {
      expect(blockToneClass(p)).toContain("--block-shadow:var(--on-ink)");
    }
    expect(blockToneClass("YouTube")).not.toContain("--block-shadow");
  });

  it("has an ink tone (errors, checking) and a lime tone (done) with ink text", () => {
    expect(blockToneClass("ink")).toContain("bg-ink");
    expect(blockToneClass("done")).toContain("bg-lime");
    expect(blockToneClass("done")).toContain("text-ink");
  });

  it("falls back to the neutral colour for a platform it does not know", () => {
    expect(blockToneClass("Mastodon" as Platform)).toContain("bg-platform-link");
  });
});
