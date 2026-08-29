# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for OmniFlow — packages the local Flask server + built React
# frontend + vendored ffmpeg into a standalone macOS .app that each end user
# installs and runs 100% on their own machine (no owner server involved).
#
# Build:  pyinstaller OmniFlow.spec --noconfirm
# Output: dist/OmniFlow.app
import os
import platform
import shutil

from PyInstaller.utils.hooks import collect_all

# Two vendored ffmpeg binaries live at the repo root: `ffmpeg` (arm64-native,
# built with dylibbundler from Homebrew's own ffmpeg so it's self-contained
# via its sibling ffmpeg-libs/ dylibs - no Homebrew needed at runtime; see
# MISTAKES.md 2026-08-29) for Apple Silicon, and `ffmpeg-x86_64` (statically
# linked codecs, zero external dylib deps) for Intel. Build on the machine
# matching the target architecture - this spec picks the matching source
# automatically via platform.machine(), so the same spec produces a
# correctly-native app on either kind of Mac without manual file-swapping.
# The bundled file must always be literally named "ffmpeg"
# (get_ffmpeg_path()'s resource_path("ffmpeg") expectation), so the chosen
# source is staged under that name before PyInstaller ever sees it.
_IS_ARM64 = platform.machine() == "arm64"
_FFMPEG_SOURCE = "ffmpeg" if _IS_ARM64 else "ffmpeg-x86_64"
_STAGE_DIR = ".ffmpeg_stage"
_STAGED_FFMPEG = os.path.join(_STAGE_DIR, "ffmpeg")
os.makedirs(_STAGE_DIR, exist_ok=True)
shutil.copy2(_FFMPEG_SOURCE, _STAGED_FFMPEG)
os.chmod(_STAGED_FFMPEG, 0o755)

datas = [
    ("frontend/dist", "frontend/dist"),  # the built UI server.py serves
    (_STAGED_FFMPEG, "."),               # vendored ffmpeg (get_ffmpeg_path restores +x)
]
if _IS_ARM64:
    # The arm64 build is only self-contained because its Mach-O load
    # commands point at @executable_path/libs/*.dylib (dylibbundler output) -
    # without bundling ./libs as a sibling of the executable too, it crashes
    # immediately with "Library not loaded" (confirmed live 2026-08-29,
    # MISTAKES.md - a folder-name mismatch reproduced exactly this). The
    # x86_64 binary needs no equivalent - confirmed via `otool -L` it only
    # links system frameworks (its codecs are statically linked in).
    datas.append(("libs/*.dylib", "libs"))
binaries = []
hiddenimports = []

# yt-dlp loads its extractors dynamically, and pywebview's macOS backend pulls
# in pyobjc — both need everything collected or the frozen app breaks at runtime.
# browser_cookie3 is imported lazily (inside cookiefiles_from_browsers) and pulls
# in C-extension deps (lz4, pycryptodomex); collect it so the frozen app can still
# auto-extract Instagram cookies from the user's browser. curl_cffi wraps a
# native libcurl-impersonate binary yt-dlp uses to impersonate a real
# browser's TLS/HTTP fingerprint (see requirements.txt) - without collecting
# it explicitly the frozen app would silently lack impersonation even though
# curl_cffi is installed at build time.
for pkg in ("yt_dlp", "webview", "browser_cookie3", "curl_cffi"):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

a = Analysis(
    ["desktop_app.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["customtkinter", "cairosvg", "tkinter"],  # legacy Tkinter app only
    noarchive=False,
)
pyz = PYZ(a.pure)

# App icon (macOS). A multi-resolution .icns (16px→1024px) generated from
# Assets/Logo/Logo-White.png so it stays crisp at every Finder/Dock size.
APP_ICON = "Assets/Logo/Logo-White.icns"

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="OmniFlow",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=APP_ICON,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="OmniFlow",
)

app = BUNDLE(
    coll,
    name="OmniFlow.app",
    icon=APP_ICON,
    bundle_identifier="com.omniflow.app",
    info_plist={
        "NSHighResolutionCapable": True,
        "CFBundleShortVersionString": "1.0.0",
        "LSMinimumSystemVersion": "11.0",
    },
)
