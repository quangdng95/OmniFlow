import fs from "node:fs";
import path from "node:path";
import type { Plugin, ResolvedConfig } from "vite";

// The Home Screen icon must not depend on a second network request.
//
// "Add to Home Screen" on iPhone downloads the apple-touch-icon at that moment and draws a plain letter tile
// when the file does not arrive in time or at all. With the icon written into the page itself (a data: URI)
// there is nothing to download. The file-based icons stay as fallbacks (other sizes, other browsers, and the
// default /apple-touch-icon.png probe), and the web app manifest carries its icons inline too.

const dataUri = (file: string): string => `data:image/png;base64,${fs.readFileSync(file).toString("base64")}`;

const APPLE_TOUCH_LINK = /(<link rel="apple-touch-icon" sizes="180x180" href=")[^"]*(" \/>)/;

export function inlineIconsInHtml(html: string, publicDir: string): string {
  if (!APPLE_TOUCH_LINK.test(html)) {
    throw new Error('index.html has no <link rel="apple-touch-icon" sizes="180x180" ...> to inline');
  }
  const fallbacks = ["167", "152"]
    .map((size) => `\n    <link rel="apple-touch-icon" sizes="${size}x${size}" href="/apple-touch-icon-${size}.png?v=4" />`)
    .join("");
  return html.replace(APPLE_TOUCH_LINK, (_match, open: string, close: string) => `${open}${dataUri(path.join(publicDir, "apple-touch-icon.png"))}${close}${fallbacks}`);
}

interface ManifestIcon {
  src: string;
  sizes: string;
  type?: string;
  purpose?: string;
}

export function inlineIconsInManifest(manifestText: string, publicDir: string): string {
  const manifest = JSON.parse(manifestText) as { icons: ManifestIcon[] };
  manifest.icons = manifest.icons.map((icon) => {
    const file = path.join(publicDir, icon.src.split("?")[0].replace(/^\//, ""));
    // The 512 px maskable icon is the same picture as the "any" one: the small file keeps the manifest short.
    if (icon.purpose === "maskable") {
      return { ...icon, src: dataUri(path.join(publicDir, "icon-192.png")), sizes: "192x192" };
    }
    return { ...icon, src: dataUri(file) };
  });
  return JSON.stringify(manifest);
}

export default function inlineIcons(): Plugin {
  let resolved: ResolvedConfig;
  return {
    name: "vidrop-inline-icons",
    apply: "build",
    configResolved(config) {
      resolved = config;
    },
    transformIndexHtml(html) {
      return inlineIconsInHtml(html, resolved.publicDir);
    },
    closeBundle() {
      const manifest = path.resolve(resolved.root, resolved.build.outDir, "manifest.webmanifest");
      if (fs.existsSync(manifest)) {
        fs.writeFileSync(manifest, inlineIconsInManifest(fs.readFileSync(manifest, "utf8"), resolved.publicDir));
      }
    },
  };
}
