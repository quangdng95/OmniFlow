# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for OmniFlow — packages the local Flask server + built React
# frontend + vendored ffmpeg into a standalone macOS .app that each end user
# installs and runs 100% on their own machine (no owner server involved).
#
# Build:  pyinstaller OmniFlow.spec --noconfirm
# Output: dist/OmniFlow.app
from PyInstaller.utils.hooks import collect_all

datas = [
    ("frontend/dist", "frontend/dist"),  # the built UI server.py serves
    ("ffmpeg", "."),                     # vendored ffmpeg (get_ffmpeg_path restores +x)
]
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
