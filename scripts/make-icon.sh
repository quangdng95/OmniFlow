#!/bin/bash
# Regenerates the Mac app icon: Assets/Logo/ViDrop-1024.png and Assets/Logo/ViDrop.icns.
#
# The artwork is FULL-BLEED: the yellow (--signal #ffd60a) fills the whole 1024x1024
# canvas edge to edge - no padding, no rounded corners, no shadow, fully opaque - with
# the black (--ink #0a0a0a) arrow-and-bar glyph centred at the same proportions as the
# logo (about 47% wide, 50% tall, well inside the area macOS keeps when it masks an icon).
# macOS applies its own corner mask to a full-bleed icon; an icon that carries a
# transparent border of its own gets set on a grey plate instead (macOS 26 "Tahoe").
#
# Needs Google Chrome (headless screenshot) and the macOS tools sips + iconutil.
# Usage (from the repo root):  ./scripts/make-icon.sh
set -euo pipefail
cd "$(dirname "$0")/.."

CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# Same geometry as frontend/src/assets/logo-icon.svg, scale 1, centred on the canvas.
cat > "$WORK/icon.html" <<'HTML'
<!doctype html><html><body style="margin:0;background:#ffd60a">
<svg width="1024" height="1024" viewBox="0 0 512 512" xmlns="http://www.w3.org/2000/svg" style="display:block">
<rect width="512" height="512" fill="#ffd60a"/>
<g transform="translate(0 -17)" fill="#0a0a0a"><path d="M136 144H376L256 352Z"/><rect x="150" y="372" width="212" height="30"/></g>
</svg></body></html>
HTML
"$CHROME" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1 \
  --window-size=1024,1024 --screenshot="$WORK/shot.png" "file://$WORK/icon.html" >/dev/null 2>&1

# The page background is opaque, so Chrome writes a plain RGB PNG (colour type 2): the icon
# has no alpha channel at all. Refuse to continue if that ever stops being true.
python3 - "$WORK/shot.png" <<'PY'
import struct, sys
width, height, depth, colour_type = struct.unpack(">IIBB", open(sys.argv[1], "rb").read()[16:26])
assert (width, height, depth, colour_type) == (1024, 1024, 8, 2), f"expected a 1024x1024 RGB PNG, got {(width, height, depth, colour_type)}"
PY
cp "$WORK/shot.png" Assets/Logo/ViDrop-1024.png

ICONSET="$WORK/ViDrop.iconset"
mkdir "$ICONSET"
for size in 16 32 128 256 512; do
  sips -z "$size" "$size" Assets/Logo/ViDrop-1024.png --out "$ICONSET/icon_${size}x${size}.png" >/dev/null
  sips -z "$((size * 2))" "$((size * 2))" Assets/Logo/ViDrop-1024.png --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o Assets/Logo/ViDrop.icns
echo "Wrote Assets/Logo/ViDrop-1024.png and Assets/Logo/ViDrop.icns"
