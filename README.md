<div align="center">
  <img src="Assets/Logo/Logo.png" alt="OmniFlow logo" width="120" />

  # OmniFlow

  **All-in-one video, audio & image downloader for macOS.**

  Paste a link. Get the file. No watermarks, no ads, no anti-bot dead ends.

  [![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
  [![Platform: macOS](https://img.shields.io/badge/platform-macOS-lightgrey.svg)](#installation)
</div>

---

## What it does

OmniFlow extracts and downloads high-quality, watermark-free video, audio, and images from the
platforms creators, designers, and researchers actually pull reference material from:

<p align="center">
  <img src="Assets/Tags/Youtube.svg" height="28" alt="YouTube" />
  <img src="Assets/Tags/Tiktok.svg" height="28" alt="TikTok" />
  <img src="Assets/Tags/Instagram.svg" height="28" alt="Instagram" />
  <img src="Assets/Tags/Facebook.svg" height="28" alt="Facebook" />
  <img src="Assets/Tags/Rednote.svg" height="28" alt="RedNote" />
  <img src="Assets/Tags/Linked.svg" height="28" alt="LinkedIn" />
  <img src="Assets/Tags/Threads.svg" height="28" alt="Threads" />
  <img src="Assets/Tags/x.com.svg" height="28" alt="X (Twitter)" />
</p>

**YouTube · TikTok · Instagram · Facebook · RedNote (Xiaohongshu) · LinkedIn · Threads · X (Twitter)**

## Features

- **Single or bulk downloads** — one video, or an entire YouTube playlist/channel, Instagram
  carousel, or Instagram Story, in one paste.
- **Automatic link detection** — OmniFlow figures out whether a link is a single item or a
  multi-item source; you never have to declare it.
- **Per-item control** — in a playlist or carousel, download everything at once, hand-pick a
  subset, or retry a single failed item.
- **Real quality, no re-encoding tax** — H.264/AAC MP4 output that plays natively in QuickLook
  and QuickTime, with fast parallel fragment downloads and a stream-copy merge (not a full
  transcode) so exports finish quickly.
- **Live progress** — per-item and overall download progress, with cancel support.
- **Runs entirely on your Mac** — no central server, no upload of your links or cookies anywhere.

## Installation

1. Download the latest `OmniFlow.dmg` from [Releases](../../releases).
2. Open the `.dmg` and drag **OmniFlow** into `Applications`.
3. On first launch, macOS may warn that the app is from an unidentified developer (it isn't
   notarized) — right-click the app and choose **Open** once to bypass this.

Prefer to build it yourself? See [Building from source](#building-from-source) below.

## Usage

1. Paste a link into OmniFlow (from the clipboard, or type/paste manually).
2. OmniFlow detects the platform and whether it's a single item or a batch.
3. Pick a quality (Best, 1080p, 720p, 480p, Audio Only, …) — or, for a batch, select which
   items you want.
4. Hit **Download** and watch progress in real time.
5. The finished file lands in your configured download folder (defaults to `~/Downloads`).

Some platforms (Instagram, Threads) need a logged-in browser session to resolve private/gated
content — OmniFlow reads this automatically from your local browser cookies; no manual export
needed.

## Building from source

**Requirements:** Node.js, Python 3.9+, npm.

```bash
# clone and enter the repo
git clone https://github.com/quangdng95/OnmiDown.git
cd OnmiDown

# one-time setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd frontend && npm install && cd ..
```

**Run in dev mode** (hot-reload, Flask backend on `:5001` + Vite frontend on `:5173`):

```bash
./dev.sh
```

**Build the standalone macOS app** (produces `dist/OmniFlow.app` and `dist/OmniFlow.dmg`):

```bash
./build.sh
```

## Tech stack

- **Backend:** Python, Flask, [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) (called in-process),
  vendored `ffmpeg` for remuxing.
- **Frontend:** React 19, TypeScript, Vite, Tailwind CSS, [shadcn/ui](https://ui.shadcn.com).
- **Desktop shell:** [`pywebview`](https://pywebview.flowrl.com), packaged with PyInstaller.

## Disclaimer

OmniFlow is built for **personal, fair-use** purposes — research, study, and archiving your own
reference material. You are responsible for the copyright status of anything you download. This
project is not intended for mass scraping or for re-uploading downloaded content for profit, and
it is not affiliated with, endorsed by, or liable for changes made by any of the source platforms
(YouTube, Meta, RedNote, etc.) that may break a feature.

## License

Licensed under the [Apache License 2.0](LICENSE).
