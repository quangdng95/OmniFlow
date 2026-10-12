import { describe, expect, it } from "vitest";
import { translations } from "./translations";

// Walk both trees and list every dotted path, so a key added to one language
// but forgotten in the other (or left empty) fails here instead of in the UI.
const paths = (value: unknown, prefix = ""): string[] => {
  if (Array.isArray(value)) return value.flatMap((v, i) => paths(v, `${prefix}[${i}]`));
  if (value && typeof value === "object") {
    return Object.entries(value).flatMap(([k, v]) => paths(v, prefix ? `${prefix}.${k}` : k));
  }
  return [prefix];
};

const leaves = (value: unknown, prefix = ""): [string, unknown][] => {
  if (Array.isArray(value)) return value.flatMap((v, i) => leaves(v, `${prefix}[${i}]`));
  if (value && typeof value === "object") {
    return Object.entries(value).flatMap(([k, v]) => leaves(v, prefix ? `${prefix}.${k}` : k));
  }
  return [[prefix, value]];
};

describe("translations", () => {
  it("English and Vietnamese have exactly the same keys", () => {
    expect(paths(translations.vi).sort()).toEqual(paths(translations.en).sort());
  });

  it.each(["en", "vi"] as const)("%s has no empty strings", (lang) => {
    const empty = leaves(translations[lang]).filter(([, v]) => typeof v === "string" && v.trim() === "");
    expect(empty.map(([k]) => k)).toEqual([]);
  });

  it.each(["en", "vi"] as const)("%s hero is two fixed lines, and the old single tagline is gone", (lang) => {
    const home = translations[lang].header.home;
    expect(home.taglineLines).toHaveLength(2);
    expect(home.taglineLines.every((l) => l.length > 0)).toBe(true);
    expect("tagline" in home).toBe(false);
  });

  it.each(["en", "vi"] as const)("%s home content has 3 steps and 4 FAQ entries", (lang) => {
    const home = translations[lang].home;
    expect(home.steps).toHaveLength(3);
    expect(home.faqs).toHaveLength(4);
    expect(home.faqs.every((f) => f.q && f.a)).toBe(true);
  });

  it("keeps placeholders in the same form in both languages", () => {
    const placeholders = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort();
    const en = leaves(translations.en);
    const vi = new Map(leaves(translations.vi));
    for (const [key, value] of en) {
      if (typeof value !== "string") continue;
      expect(placeholders(String(vi.get(key) ?? ""))).toEqual(placeholders(value));
    }
  });
});
