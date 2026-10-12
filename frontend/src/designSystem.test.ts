/// <reference types="node" />
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

// Static checks on index.css: the V3 tokens, the accessibility rules and the
// self-hosted fonts must stay in place (a jsdom render can't see any of them).
const here = resolve(process.cwd(), "src");
const css = readFileSync(resolve(here, "index.css"), "utf8");
const fontsDir = resolve(here, "../public/fonts");

const tokenValue = (name: string): string | undefined =>
  new RegExp(`--${name}:\\s*([^;]+);`).exec(css)?.[1].trim();

const luminance = (hex: string): number => {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const contrast = (a: string, b: string): number => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};

describe("design tokens", () => {
  it("defines the V3 palette once, as raw values", () => {
    for (const t of ["ink", "on-ink", "paper", "brand", "signal", "lime", "ink-muted", "ink-hover", "invalid"]) {
      expect(tokenValue(t), `--${t}`).toMatch(/^#[0-9a-f]{6}$/i);
    }
  });

  it("wires the shadcn variables to the tokens and squares the corners", () => {
    expect(tokenValue("background")).toBe("var(--paper)");
    expect(tokenValue("foreground")).toBe("var(--ink)");
    expect(tokenValue("primary")).toBe("var(--ink)");
    expect(tokenValue("ring")).toBe("var(--brand)");
    expect(tokenValue("radius")).toBe("0rem");
  });

  it("every platform block colour gives >= 4.5:1 with white text", () => {
    const resolveHex = (name: string): string => {
      const v = tokenValue(name)!;
      const ref = /^var\(--([\w-]+)\)$/.exec(v);
      return ref ? resolveHex(ref[1]) : v;
    };
    for (const p of ["youtube", "instagram", "facebook", "rednote", "linkedin", "tiktok", "x", "threads", "link"]) {
      expect(contrast("#ffffff", resolveHex(`platform-${p}`)), p).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("text pairs meet WCAG AA", () => {
    expect(contrast("#0a0a0a", "#fafaf7")).toBeGreaterThanOrEqual(4.5); // body
    expect(contrast("#4a4a4a", "#fafaf7")).toBeGreaterThanOrEqual(4.5); // muted / placeholder
    expect(contrast("#0a0a0a", "#ffd60a")).toBeGreaterThanOrEqual(4.5); // paste button + selection
    expect(contrast("#0a0a0a", "#c6ff3d")).toBeGreaterThanOrEqual(4.5); // done block
    expect(contrast("#ffffff", "#0a0a0a")).toBeGreaterThanOrEqual(4.5);
    expect(contrast("#1738ff", "#fafaf7")).toBeGreaterThanOrEqual(3); // focus ring + borders (non-text)
  });
});

describe("accessibility rules", () => {
  it("has a visible keyboard focus outline outside any layer (so it beats outline-none)", () => {
    const outside = css.replace(/@layer base \{[\s\S]*$/, "");
    expect(outside).toMatch(/:focus-visible\s*\{[^}]*outline:\s*4px solid var\(--ring\)/);
  });

  it("respects prefers-reduced-motion", () => {
    expect(css).toMatch(/@media \(prefers-reduced-motion: reduce\)/);
  });

  it("styles ::selection with ink on signal yellow and keeps labels selectable", () => {
    expect(css).toMatch(/::selection\s*\{[^}]*background:\s*var\(--signal\)[^}]*color:\s*var\(--ink\)/);
    expect(css).toMatch(/\[data-slot="label"\]\s*\{[^}]*user-select:\s*text/);
  });

  it("never switches text selection off globally", () => {
    for (const selector of ["html", "body", "#root", "\\*"]) {
      expect(css).not.toMatch(new RegExp(`(^|\\n)${selector}\\s*\\{[^}]*user-select:\\s*none`));
    }
  });

  it("keeps body copy at 16px or more", () => {
    expect(css).toMatch(/body\s*\{[^}]*font-size:\s*1\.0625rem/);
  });

  it("shares one height token between the language switch and the menu", () => {
    expect(tokenValue("control-h")).toBe("3rem");
  });
});

describe("self-hosted fonts", () => {
  it.each([
    "be-vietnam-pro-400-vietnamese.woff2",
    "be-vietnam-pro-500-vietnamese.woff2",
    "be-vietnam-pro-700-vietnamese.woff2",
    "be-vietnam-pro-400-latin.woff2",
    "space-grotesk-700-vietnamese.woff",
    "space-grotesk-700-latin.woff",
  ])("ships %s, and index.css points at it", (file) => {
    expect(existsSync(resolve(fontsDir, file))).toBe(true);
    expect(css).toContain(`/fonts/${file}`);
  });

  it("uses the display font for headings and the body font for text", () => {
    expect(css).toMatch(/--font-display:\s*"Space Grotesk"/);
    expect(css).toMatch(/--font-sans:\s*"Be Vietnam Pro"/);
  });
});
