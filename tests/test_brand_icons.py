"""The icons must stay opaque, square, brand-yellow, and the right size (scripts/gen-icons.sh)."""

import os
import struct
import zlib

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC = os.path.join(ROOT, "frontend", "public")

SIZES = {
    "favicon-16.png": (16, 16),
    "favicon-32.png": (32, 32),
    "apple-touch-icon.png": (180, 180),
    "icon-192.png": (192, 192),
    "icon-512.png": (512, 512),
    "icon-maskable-512.png": (512, 512),
    "og-image.png": (1200, 630),
}


def _png(path):
    data = open(path, "rb").read()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    width, height, depth, colour_type = struct.unpack(">IIBB", data[16:26])
    pos, idat = 8, b""
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos : pos + 8])
        if kind == b"IDAT":
            idat += data[pos + 8 : pos + 8 + length]
        pos += 12 + length
    return width, height, depth, colour_type, zlib.decompress(idat)


def _rgb_at(raw, width, x, y):
    # Only filter type 0/1/2/3/4 reconstruction is needed for a corner pixel of an opaque RGB image;
    # decode the whole first and the pixel's row properly.
    stride = width * 3
    prev = bytearray(stride)
    for row in range(y + 1):
        base = row * (stride + 1)
        ftype, line = raw[base], bytearray(raw[base + 1 : base + 1 + stride])
        for i in range(stride):
            a = line[i - 3] if i >= 3 else 0
            b = prev[i]
            c = prev[i - 3] if i >= 3 else 0
            if ftype == 1:
                line[i] = (line[i] + a) & 255
            elif ftype == 2:
                line[i] = (line[i] + b) & 255
            elif ftype == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif ftype == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                line[i] = (line[i] + pred) & 255
        prev = line
    return tuple(prev[x * 3 : x * 3 + 3])


@pytest.mark.parametrize("name,size", SIZES.items())
def test_icon_is_opaque_rgb_at_the_right_size(name, size):
    width, height, depth, colour_type, _ = _png(os.path.join(PUBLIC, name))
    assert (width, height) == size
    assert (depth, colour_type) == (8, 2)  # 8-bit RGB: no alpha channel, so no transparent corners


@pytest.mark.parametrize("name", ["favicon-32.png", "apple-touch-icon.png", "icon-192.png", "icon-512.png", "icon-maskable-512.png"])
def test_square_icons_are_solid_brand_yellow_edge_to_edge(name):
    width, height, _, _, raw = _png(os.path.join(PUBLIC, name))
    assert _rgb_at(raw, width, 0, 0) == (255, 214, 10)  # no rounded corner, no padding
    assert _rgb_at(raw, width, width - 1, height - 1) == (255, 214, 10)
    assert _rgb_at(raw, width, width - 1, 0) == (255, 214, 10)


def test_one_source_feeds_every_svg_and_the_ico_has_three_sizes():
    source = open(os.path.join(PUBLIC, "brand", "logo.svg")).read()
    assert "#ffd60a" in source and "rx=" not in source  # square, brand yellow
    assert open(os.path.join(PUBLIC, "favicon.svg")).read() == source
    assert open(os.path.join(ROOT, "frontend", "src", "assets", "logo-icon.svg")).read() == source
    ico = open(os.path.join(PUBLIC, "favicon.ico"), "rb").read()
    reserved, kind, count = struct.unpack("<HHH", ico[:6])
    assert (reserved, kind, count) == (0, 1, 3)
    assert sorted(ico[6 + 16 * i] for i in range(3)) == [16, 32, 48]


def test_html_and_manifest_point_at_the_icons():
    html = open(os.path.join(ROOT, "frontend", "index.html")).read()
    for needle in ('rel="apple-touch-icon"', 'rel="manifest"', 'rel="icon"', 'content="#ffd60a"', 'og:image', 'apple-mobile-web-app-title" content="ViDrop"'):
        assert needle in html, needle
