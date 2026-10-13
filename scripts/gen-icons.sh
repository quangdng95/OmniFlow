#!/bin/bash
# Regenerates every ViDrop icon from the ONE source, frontend/public/brand/logo.svg:
#   a solid #ffd60a square (no rounded corners, no padding, no alpha) with the black arrow-and-bar
#   glyph (about 47% wide, 50% tall, inside the 60% maskable safe zone).
# Outputs (all opaque RGB PNG except the SVG/ICO):
#   frontend/public/favicon.svg, favicon.ico (16/32/48), favicon-16.png, favicon-32.png,
#   apple-touch-icon.png (180), icon-192.png, icon-512.png, icon-maskable-512.png, og-image.png (1200x630),
#   frontend/src/assets/logo-icon.svg (header logo), docs/logo.png (README, 240).
# The Mac app icon (Assets/Logo/ViDrop.icns) has the same geometry; scripts/make-icon.sh builds it.
# Needs Google Chrome (headless screenshot), sips and python3. Usage (repo root): ./scripts/gen-icons.sh
set -euo pipefail
cd "$(dirname "$0")/.."

CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
SRC="frontend/public/brand/logo.svg"
PUB="frontend/public"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
ROOT="$PWD"

shot() { # shot <html> <out.png> <width> <height>
  "$CHROME" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1 \
    --window-size="$3,$4" --screenshot="$2" "file://$1" >/dev/null 2>&1
}

# 1. One 1024 master from the SVG (an opaque page, so Chrome writes plain RGB).
cat > "$WORK/master.html" <<HTML
<!doctype html><html><body style="margin:0;background:#ffd60a"><img src="file://$ROOT/$SRC" width="1024" height="1024" style="display:block"></body></html>
HTML
shot "$WORK/master.html" "$WORK/master.png" 1024 1024

# 2. Every size is a downscale of the master.
size() { sips -z "$2" "$2" "$WORK/master.png" --out "$1" >/dev/null; }
size "$PUB/favicon-16.png" 16
size "$PUB/favicon-32.png" 32
size "$WORK/favicon-48.png" 48
size "$PUB/apple-touch-icon.png" 180
size "$PUB/icon-192.png" 192
size "$PUB/icon-512.png" 512
size "$PUB/icon-maskable-512.png" 512   # same art: the glyph already sits inside the 60% safe zone
size "docs/logo.png" 240

# 3. SVGs are copies of the source.
cp "$SRC" "$PUB/favicon.svg"
cp "$SRC" frontend/src/assets/logo-icon.svg

# 4. favicon.ico = PNG-compressed 16 + 32 + 48.
python3 - "$PUB/favicon-16.png" "$PUB/favicon-32.png" "$WORK/favicon-48.png" "$PUB/favicon.ico" <<'PY'
import struct, sys
*pngs, out = sys.argv[1:]
data = [open(p, "rb").read() for p in pngs]
head = struct.pack("<HHH", 0, 1, len(data))
offset = 6 + 16 * len(data)
entries, blobs = b"", b""
for png in data:
    w, h = struct.unpack(">II", png[16:24])
    entries += struct.pack("<BBBBHHII", w % 256, h % 256, 0, 0, 1, 32, len(png), offset + len(blobs))
    blobs += png
open(out, "wb").write(head + entries + blobs)
PY

# 5. Social card 1200x630: the logo on the brand yellow with the wordmark.
cat > "$WORK/og.html" <<HTML
<!doctype html><html><head><style>
@font-face { font-family: SG; font-weight: 700; src: url("file://$ROOT/$PUB/fonts/space-grotesk-700-latin.woff"); }
body { margin: 0; width: 1200px; height: 630px; background: #ffd60a; display: flex; align-items: center; gap: 56px; padding: 0 96px; box-sizing: border-box; font-family: SG, sans-serif; color: #0a0a0a; }
img { width: 330px; height: 330px; display: block; flex: none; }
h1 { margin: 0; font-size: 150px; letter-spacing: -6px; line-height: 1; }
p { margin: 14px 0 0; font-size: 40px; letter-spacing: -1px; font-weight: 700; }
</style></head><body><img src="file://$ROOT/$SRC"><div><h1>ViDrop</h1><p>All-in-one video downloader</p></div></body></html>
HTML
shot "$WORK/og.html" "$PUB/og-image.png" 1200 630

echo "Icons regenerated from $SRC"
