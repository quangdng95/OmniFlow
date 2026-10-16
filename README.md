<div align="center">
  <img src="docs/logo.png" alt="ViDrop" width="120" />

  # ViDrop

  **All-in-one video, audio & image downloader for macOS.**

  Paste a link. Get the file. No watermarks, no ads, no anti-bot dead ends.

  [![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
  [![Platform: macOS](https://img.shields.io/badge/platform-macOS-lightgrey.svg)](#installation)
  [![Latest Release](https://img.shields.io/github/v/release/quangdng95/ViDrop)](../../releases/latest)

  **🇬🇧 English&nbsp;&nbsp;|&nbsp;&nbsp;[🇻🇳 Tiếng Việt](README.vi.md)**
</div>

---

## Download

Not sure which chip your Mac has? Apple menu (top-left) → **About This Mac**.

<p align="center">
  <a href="https://github.com/quangdng95/ViDrop/releases/latest/download/ViDrop-AppleSilicon.dmg"><img src="https://img.shields.io/badge/Download-Apple_Silicon-black?style=for-the-badge&logo=apple" alt="Download for Apple Silicon (M1/M2/M3/M4)" /></a>
  <a href="https://github.com/quangdng95/ViDrop/releases/latest/download/ViDrop-Intel.dmg"><img src="https://img.shields.io/badge/Download-Intel_Mac-black?style=for-the-badge&logo=apple" alt="Download for Intel Mac" /></a>
</p>

These links always point at the latest release. See [Installation](#installation) below for what to do after downloading — including the one-time macOS security prompts on first launch.

---

## What it does

ViDrop extracts and downloads high-quality, watermark-free video, audio, and images from the
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

**YouTube · TikTok · Instagram · Facebook · RedNote (Xiaohongshu) · LinkedIn · Threads · Pinterest · X (Twitter)**

| Platform | What works | Notes |
|---|---|---|
| YouTube | Video up to 4K, audio only (MP3), Mix, playlist, channel | May need your Chrome sign-in: Settings → YouTube sign-in |
| TikTok | Video, audio only (MP3), Photo Mode slideshow | Photo Mode uses the third-party service tikwm.com |
| Instagram | Reel, photo post, carousel | Needs a login in your browser. Profile / Reels lists are often refused by Instagram |
| Facebook | Video, Reel, `share/r/` links | |
| X (Twitter) | Video post | |
| Threads | Video post, image post | Needs a login in your browser |
| Pinterest | Board (every pin, images and videos), single pin | Public boards need no login. A private board needs the Mac app and a Pinterest login in your browser |
| LinkedIn | Video post, image post, slide-deck (PDF) — every page as an image | `lnkd.in` links work. No login needed |
| RedNote (Xiaohongshu) | Video note, image note | Needs a login in your browser. Share links expire, so copy a fresh one |

Every row was checked with real links. The full table, with what was and wasn't tested, is in
[docs/PLATFORM_SUPPORT.md](docs/PLATFORM_SUPPORT.md).

## Features

- **Single or bulk downloads** — one video, or an entire YouTube playlist/channel, Instagram
  carousel, or Instagram Story, in one paste.
- **Automatic link detection** — ViDrop figures out whether a link is a single item or a
  multi-item source; you never have to declare it.
- **Per-item control** — in a playlist or carousel, download everything at once, hand-pick a
  subset, or retry a single failed item.
- **Plays everywhere on your Mac** — H.264/AAC MP4 output that plays natively in QuickLook
  and QuickTime. Up to 1080p it uses fast parallel fragment downloads and a stream-copy merge
  (not a full transcode). 1440p and 4K are converted to H.264 after the download, using the Mac's hardware encoder
  when that is faster; tick **Keep original codec** to skip the conversion and save a `.mkv`
  (it may not open in QuickTime or on an iPhone).
- **Live progress** — per-item and overall download progress, with cancel support.
- **Runs on your Mac** — your links and cookies stay on your machine (one exception for TikTok,
  see [Privacy](#privacy)).

## Installation

1. Download the `.dmg` matching your Mac's chip — see [Download](#download) above, or grab it
   from [Releases](../../releases/latest):
   - **ViDrop-AppleSilicon.dmg** — for M1/M2/M3/M4 Macs
   - **ViDrop-Intel.dmg** — for Intel Macs
2. Open the `.dmg` and drag **ViDrop** into `Applications`.
3. On first launch, macOS will show one or two security prompts (an "unidentified developer"
   warning, and — only if you plan to download from Instagram, Threads or RedNote, or turn on
   YouTube sign-in — a Keychain permission request). Both are normal, one-time, and explained
   step-by-step in [First Launch & macOS Security Warnings](docs/FIRST_LAUNCH.md).

**Coming from the old app (OmniFlow)?** ViDrop is a separate app. The first time you open it, it
copies your settings from the old app's folder and leaves that folder as it was, so you can keep
the old app until you're happy. macOS treats ViDrop as a new app, so it asks for Keychain access
again. Your History starts empty.

Prefer to build it yourself? See [Building from source](#building-from-source) below.

## Usage

1. Paste a link into ViDrop (from the clipboard, or type/paste manually).
2. ViDrop detects the platform and whether it's a single item or a batch.
3. Pick a quality (Best, 1080p, 720p, 480p, Audio Only, …) — or, for a batch, select which
   items you want.
4. Hit **Download** and watch progress in real time.
5. The finished file lands in your configured download folder (defaults to `~/Downloads`).

Some platforms (Instagram, Threads, RedNote) need a logged-in browser session to resolve private/gated
content — ViDrop reads this automatically from your local browser cookies; no manual export
needed. If YouTube asks you to sign in, choose your Chrome profile in **Settings → YouTube sign-in**
(off by default).

**Example:**

```
Paste:  https://www.youtube.com/watch?v=dQw4w9WgXcQ
Pick:   Best
Get:    Never Gonna Give You Up.mp4  (in ~/Downloads)
```

Not sure what to try first? [**Example Links**](docs/EXAMPLE_LINKS.md) has one ready-to-paste
example per supported platform.

## Building from source

**Requirements:** Node.js, Python 3.9+, npm.

```bash
# clone and enter the repo
git clone https://github.com/quangdng95/ViDrop.git
cd ViDrop

# one-time setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd frontend && npm install && cd ..
```

**Run in dev mode** (hot-reload, Flask backend on `:5001` + Vite frontend on `:5173`):

```bash
./scripts/dev.sh
```

**Build the standalone macOS app** (produces `release/v<version>/ViDrop-AppleSilicon.dmg`, or `ViDrop-Intel.dmg` on an Intel Mac, plus the signed app under `release/v<version>/_build/`):

```bash
./scripts/build.sh
```

## Tech stack

- **Backend:** Python, Flask, [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) (called in-process),
  vendored `ffmpeg` for remuxing.
- **Frontend:** React 19, TypeScript, Vite, Tailwind CSS, [shadcn/ui](https://ui.shadcn.com).
- **Desktop shell:** [`pywebview`](https://pywebview.flowrl.com), packaged with PyInstaller.

## Privacy

ViDrop runs entirely on your Mac. It does **not**:

- Store or route your downloads through any external server
- Track or log your download history
- Collect or transmit personal data anywhere

One exception: when a TikTok link can't be read directly, ViDrop sends that link to the
third-party service tikwm.com to resolve it. This page describes the Mac app. The hosted web
version processes the links you paste on its own server.

Browser cookies (used to resolve Instagram, Threads and RedNote content) are read locally and
never leave your machine.

## Roadmap

What is still open, stated plainly.

- [ ] **Code signing and notarization**: macOS still warns on first launch (right-click → Open). It needs a paid Apple Developer account; see [First Launch](docs/FIRST_LAUNCH.md).
- [ ] **Check the video conversion choice on a real Intel Mac.** For 1440p/4K, ViDrop picks the hardware or software encoder by the chip. That rule was measured on Apple Silicon and under Rosetta 2 only.
- [ ] **Check the platforms we could not test**: Instagram Stories and private posts, X images, RedNote, and a few link shapes. They need sample links; see [Platform support](docs/PLATFORM_SUPPORT.md).
- [ ] **Review the Terms of Use** against how the Mac app and the web version work today.
- Exploring, not committed: Windows/Linux builds, a Chrome extension, native phone apps. The web version already works in a phone browser.

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
[GitHub Issues](https://github.com/quangdng95/ViDrop/issues) — include:

- The link you were trying to download (if it's not private/sensitive)
- Your Mac's chip (Apple Silicon or Intel) and macOS version
- The contents of `errors.log`, if there is one — Settings → **Diagnostic Logs** → **Open Log
  Folder**

Have a feature request instead? Open an issue for that too.

## Disclaimer

ViDrop is built for **personal, non-commercial use** — research, study, and archiving your own
reference material. You are solely responsible for the copyright status of anything you download
and for complying with each platform's Terms of Service. The developers provide this tool "AS IS"
with zero liability for how it's used — see [DISCLAIMER.md](.github/DISCLAIMER.md) for the full legal
disclaimer and [CODE_OF_CONDUCT.md](.github/CODE_OF_CONDUCT.md) for the acceptable-use policy.

## License

Licensed under the [GNU General Public License v3.0](LICENSE).
