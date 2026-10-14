"""The product is spelled ViDrop (V and D capital) everywhere a user can see it."""

import re
import subprocess

ROOT = __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__)))

# Spellings that are NOT the product name: identifiers (vidrop.spec, com.vidrop.app, VIDROP_H264_ENCODER)
# and file names are fine, so only the display-style miscasings are caught.
WRONG = re.compile(r"\b(Vidrop|VIDrop|ViDROP|VIdrop|Vi Drop|Vi-Drop)\b")


def test_no_tracked_text_misspells_the_product_name():
    files = subprocess.run(
        ["git", "ls-files", "--", ".", ":!docs/superpowers", ":!frontend/package-lock.json", ":!frontend/public/fonts"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    offenders = []
    for name in files:
        if name.endswith((".png", ".ico", ".icns", ".woff", ".woff2", ".dylib", ".dmg")) or "vendor/ffmpeg" in name:
            continue
        try:
            text = open(f"{ROOT}/{name}", encoding="utf-8").read()
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if name != "tests/test_brand_name.py" and WRONG.search(line):
                offenders.append(f"{name}:{number}: {line.strip()[:80]}")
    assert not offenders, "Write the product name as ViDrop:\n" + "\n".join(offenders)
