"""The Mac app icon must be full-bleed: yellow edge to edge, opaque, glyph centred.

An icon with a transparent border of its own is set on a grey plate by macOS 26, so the
logo looked like a small yellow square inside a grey tile. scripts/make-icon.sh makes
the icon; these checks read the committed PNG directly (stdlib only) and the .icns header.
"""

import os
import struct
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
YELLOW = (255, 214, 10)  # --signal in frontend/src/index.css
INK = (10, 10, 10)  # --ink


def _read_png(path):
    data = open(path, "rb").read()
    pos, idat = 8, b""
    while pos < len(data):
        size, = struct.unpack(">I", data[pos:pos + 4])
        kind, body = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + size]
        if kind == b"IHDR":
            width, height, depth, colour_type = struct.unpack(">IIBB", body[:10])
        elif kind == b"IDAT":
            idat += body
        pos += 12 + size
    channels = {2: 3, 6: 4}[colour_type]
    raw, stride, prev, rows, i = zlib.decompress(idat), width * channels, bytearray(width * channels), [], 0
    for _ in range(height):
        f, line = raw[i], bytearray(raw[i + 1:i + 1 + stride])
        i += 1 + stride
        for x in range(stride):
            a = line[x - channels] if x >= channels else 0
            b = prev[x]
            c = prev[x - channels] if x >= channels else 0
            if f == 1: line[x] = (line[x] + a) & 255
            elif f == 2: line[x] = (line[x] + b) & 255
            elif f == 3: line[x] = (line[x] + ((a + b) >> 1)) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else (b if pb <= pc else c))) & 255
        rows.append(line)
        prev = line
    return width, height, colour_type, channels, rows


def _pixel(rows, channels, x, y):
    return tuple(rows[y][x * channels:x * channels + 3]), (rows[y][x * channels + 3] if channels == 4 else 255)


def test_the_icon_artwork_is_opaque_yellow_edge_to_edge():
    width, height, colour_type, channels, rows = _read_png(os.path.join(ROOT, "Assets", "Logo", "ViDrop-1024.png"))
    assert (width, height) == (1024, 1024)
    assert colour_type == 2  # plain RGB: there is no alpha channel at all
    last = width - 1
    for x, y in [(0, 0), (last, 0), (0, last), (last, last), (512, 0), (512, last), (0, 512), (last, 512)]:
        assert _pixel(rows, channels, x, y) == (YELLOW, 255), (x, y)


def test_the_glyph_is_black_centred_and_about_half_the_canvas():
    _, _, _, channels, rows = _read_png(os.path.join(ROOT, "Assets", "Logo", "ViDrop-1024.png"))
    dark = [(x, y) for y in range(0, 1024, 2) for x in range(0, 1024, 2) if sum(_pixel(rows, channels, x, y)[0]) < 300]
    xs, ys = [p[0] for p in dark], [p[1] for p in dark]
    box_width, box_height = (max(xs) - min(xs)) / 1024, (max(ys) - min(ys)) / 1024
    assert 0.45 <= box_width <= 0.50 and 0.48 <= box_height <= 0.52, (box_width, box_height)
    assert abs((min(xs) + max(xs)) / 2 - 512) <= 4 and abs((min(ys) + max(ys)) / 2 - 512) <= 4  # centred
    assert _pixel(rows, channels, 512, 330)[0] == INK  # inside the arrow head


def test_the_icns_file_is_a_real_icon_set():
    data = open(os.path.join(ROOT, "Assets", "Logo", "ViDrop.icns"), "rb").read()
    assert data[:4] == b"icns" and struct.unpack(">I", data[4:8])[0] == len(data)
    assert len(data) > 20_000
