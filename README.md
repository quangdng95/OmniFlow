<div align="center">
  <img src="Assets/Logo/Logo.png" alt="OmniFlow logo" width="120" />

  # OmniFlow

  **All-in-one video, audio & image downloader for macOS.**

  Paste a link. Get the file. No watermarks, no ads, no anti-bot dead ends.

  [![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
  [![Platform: macOS](https://img.shields.io/badge/platform-macOS-lightgrey.svg)](#installation)
  [![Latest Release](https://img.shields.io/github/v/release/quangdng95/OmniFlow)](../../releases/latest)
</div>

---

## Download

Not sure which chip your Mac has? Apple menu (top-left) → **About This Mac**.

<p align="center">
  <a href="https://github.com/quangdng95/OmniFlow/releases/latest/download/OmniFlow-AppleSilicon.dmg"><img src="https://img.shields.io/badge/Download-Apple_Silicon-black?style=for-the-badge&logo=apple" alt="Download for Apple Silicon (M1/M2/M3/M4)" /></a>
  <a href="https://github.com/quangdng95/OmniFlow/releases/latest/download/OmniFlow-Intel.dmg"><img src="https://img.shields.io/badge/Download-Intel_Mac-black?style=for-the-badge&logo=apple" alt="Download for Intel Mac" /></a>
</p>

These links always point at the latest release. See [Installation](#installation) below for what to do after downloading — including the one-time macOS security prompts on first launch.

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

| Platform | Single item | Bulk / multi-item | Notes |
|---|---|---|---|
| YouTube | ✅ Video, audio-only | ✅ Playlist, channel, Mix/Radio | |
| TikTok | ✅ Video | — | |
| Instagram | ✅ Post, Reel, photo | ✅ Carousel, Story, profile/Reels | Private content needs a logged-in browser session |
| Facebook | ✅ Reel | — | |
| RedNote (Xiaohongshu) | ✅ Video, image | — | |
| LinkedIn | ✅ Video post, image post | — | Native document/slide-deck posts not yet supported |
| Threads | ✅ Video post, image post | — | Needs a logged-in browser session |
| X (Twitter) | ✅ Video post | — | |

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

1. Download the `.dmg` matching your Mac's chip — see [Download](#download) above, or grab it
   from [Releases](../../releases/latest):
   - **OmniFlow-AppleSilicon.dmg** — for M1/M2/M3/M4 Macs
   - **OmniFlow-Intel.dmg** — for Intel Macs
2. Open the `.dmg` and drag **OmniFlow** into `Applications`.
3. On first launch, macOS will show one or two security prompts (an "unidentified developer"
   warning, and — only if you plan to download private Instagram/Threads content — a Keychain
   permission request). Both are normal, one-time, and explained step-by-step in
   [First Launch & macOS Security Warnings](docs/FIRST_LAUNCH.md).

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

**Example:**

```
Paste:  https://www.youtube.com/watch?v=dQw4w9WgXcQ
Pick:   Best
Get:    Never Gonna Give You Up.mp4  (in ~/Downloads)
```

## Building from source

**Requirements:** Node.js, Python 3.9+, npm.

```bash
# clone and enter the repo
git clone https://github.com/quangdng95/OmniFlow.git
cd OmniFlow

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

## Privacy

OmniFlow runs entirely on your Mac. It does **not**:

- Store or route your downloads through any external server
- Track or log your download history
- Collect or transmit personal data anywhere

Browser cookies (used to resolve private Instagram/Threads content) are read locally and never
leave your machine.

## Roadmap

Known gaps, tracked honestly rather than hidden.

**macOS app polish**

- [ ] Native `arm64` `ffmpeg` for the Apple Silicon build, so it no longer needs Rosetta 2 at
  runtime (the Intel build's `ffmpeg` is already native)
- [ ] Code signing + notarization, so macOS stops warning about an unidentified developer on
  first launch
- [ ] LinkedIn native document/slide-deck (PDF) post support
- [ ] Windows / Linux builds

**Platform expansion**

- [ ] Chrome extension — click a button in your browser to send the video you're watching
  straight to OmniFlow, no copy-pasting the link needed
- [ ] A convenient way to send a link to OmniFlow from your phone while it's running on your Mac
  (e.g. an iOS Shortcut, or a simple mobile-friendly page)
- [ ] Native Android app
- [ ] Native iOS app

> **On the two native mobile app items:** these are early and exploratory, not committed.
> `yt-dlp` is a Python tool, and this project's whole design deliberately avoids a central server
> (see [Disclaimer](.github/DISCLAIMER.md)) so each download runs locally, on the user's own
> machine — that constraint doesn't disappear just because the device is a phone. Both the App
> Store and Play Store have a well-documented history of rejecting or removing "video downloader"
> apps over copyright/ToS concerns, so a native mobile app may end up needing to ship outside the
> official stores (sideloading, TestFlight-style distribution) rather than assuming normal store
> availability.

## Troubleshooting

Hit a security warning on first launch, or a check/download that keeps failing? Two guides cover
this in detail, step by step:

- **[First Launch & macOS Security Warnings](docs/FIRST_LAUNCH.md)** — the "unidentified
  developer" warning and the Keychain permission prompt you may see the first time you open the
  app or download from Instagram/Threads.
- **[Troubleshooting Check/Download Failures](docs/TROUBLESHOOTING.md)** — what to do when a link
  won't check or a download keeps failing, including how to use the built-in **Diagnostic Logs**
  and **Reset App Data** tools in Settings.

If those don't resolve it, see [Support & Issues](#support--issues) below.

## Contributing

Contributions are welcome:

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/my-feature`)
3. Commit your changes
4. Push to your branch and open a Pull Request

## Support & Issues

Still stuck after checking the [Troubleshooting](#troubleshooting) guides above? Open an issue on
[GitHub Issues](https://github.com/quangdng95/OmniFlow/issues) — include:

- The link you were trying to download (if it's not private/sensitive)
- Your Mac's chip (Apple Silicon or Intel) and macOS version
- The contents of `errors.log`, if there is one — Settings → **Diagnostic Logs** → **Open Log
  Folder**

Have a feature request instead? Open an issue for that too.

## Disclaimer

OmniFlow is built for **personal, non-commercial use** — research, study, and archiving your own
reference material. You are solely responsible for the copyright status of anything you download
and for complying with each platform's Terms of Service. The developers provide this tool "AS IS"
with zero liability for how it's used — see [DISCLAIMER.md](.github/DISCLAIMER.md) for the full legal
disclaimer and [CODE_OF_CONDUCT.md](.github/CODE_OF_CONDUCT.md) for the acceptable-use policy.

## License

Licensed under the [GNU General Public License v3.0](LICENSE).
