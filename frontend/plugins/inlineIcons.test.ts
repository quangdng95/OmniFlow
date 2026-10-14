import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { inlineIconsInHtml, inlineIconsInManifest } from "./inlineIcons.ts";

const publicDir = path.resolve(__dirname, "../public");
const html = fs.readFileSync(path.resolve(__dirname, "../index.html"), "utf8");
const png = (name: string) => fs.readFileSync(path.join(publicDir, name));
const decode = (uri: string) => Buffer.from(uri.split(",")[1], "base64");

describe("inlineIconsInHtml", () => {
  const out = inlineIconsInHtml(html, publicDir);

  it("writes the real 180 px apple-touch-icon into the page as a data: URI", () => {
    const match = out.match(/<link rel="apple-touch-icon" sizes="180x180" href="(data:image\/png;base64,[^"]+)"/);
    expect(match).not.toBeNull();
    expect(decode(match![1]).equals(png("apple-touch-icon.png"))).toBe(true);
  });

  it("keeps file-based 167 and 152 px icons as fallbacks, and every other tag untouched", () => {
    expect(out).toContain('sizes="167x167" href="/apple-touch-icon-167.png?v=4"');
    expect(out).toContain('sizes="152x152" href="/apple-touch-icon-152.png?v=4"');
    expect(out).toContain('<link rel="manifest" href="/manifest.webmanifest?v=4" />');
    expect(out).toContain('<meta name="theme-color" content="#ffd60a" />');
  });

  it("fails loudly when the icon link is missing instead of shipping a page without it", () => {
    expect(() => inlineIconsInHtml("<html><head></head></html>", publicDir)).toThrow(/apple-touch-icon/);
  });

  it("the fallback files exist, are opaque RGB and have the sizes their names promise", () => {
    for (const size of [152, 167]) {
      const data = png(`apple-touch-icon-${size}.png`);
      expect(data.readUInt32BE(16)).toBe(size);
      expect(data.readUInt32BE(20)).toBe(size);
      expect(data[25]).toBe(2); // colour type 2 = RGB, no alpha
    }
  });
});

describe("inlineIconsInManifest", () => {
  const manifest = JSON.parse(inlineIconsInManifest(fs.readFileSync(path.join(publicDir, "manifest.webmanifest"), "utf8"), publicDir));

  it("keeps the app identity and gives every icon an inline picture", () => {
    expect(manifest.name).toBe("ViDrop");
    expect(manifest.display).toBe("standalone");
    for (const icon of manifest.icons) expect(icon.src.startsWith("data:image/png;base64,")).toBe(true);
  });

  it("the 'any' icons are the real 192 and 512 files; the maskable one is the small 192 picture", () => {
    const any = manifest.icons.filter((i: { purpose: string }) => i.purpose === "any");
    expect(any.map((i: { sizes: string }) => i.sizes)).toEqual(["192x192", "512x512"]);
    expect(decode(any[0].src).equals(png("icon-192.png"))).toBe(true);
    expect(decode(any[1].src).equals(png("icon-512.png"))).toBe(true);
    const maskable = manifest.icons.find((i: { purpose: string }) => i.purpose === "maskable");
    expect(maskable.sizes).toBe("192x192");
    expect(decode(maskable.src).equals(png("icon-192.png"))).toBe(true);
  });
});
