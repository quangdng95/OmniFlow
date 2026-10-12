# Vidrop – portfolio export

Three redesign directions for the Vidrop home page (V1 Command bar, V2 Workspace, V3 Bold type), packaged as
static screenshots plus a click-through prototype. Nothing here touches `frontend/src` or `design-explore/`.

## Structure

```
portfolio-export/
├─ README.md
├─ images/                 66 PNG @2x  (Vidrop_<V1|V2|V3>_<Mobile|Desktop>_<State>[_EN].png)
├─ prototype/              self-contained, no network, works from file:// or any static host
│  ├─ index.html           overview: variant tabs, phone/desktop switch, state list, VI/EN
│  ├─ v1.html  v2.html  v3.html
│  └─ fonts/               30 woff2 files (self-hosted, OFL): Manrope, IBM Plex Sans/Mono,
│                          Space Grotesk, Be Vietnam Pro (latin, latin-ext, vietnamese subsets)
└─ _src/                   build tooling and test scripts (not needed to view or host anything)
```

## Run locally

Open `prototype/index.html` directly (double-click), or serve the folder:

```bash
cd portfolio-export/prototype && python3 -m http.server 8000   # http://127.0.0.1:8000/
```

## Prototype URL parameters

| Param | Values |
|---|---|
| `state` | `empty` `analyzing` `result` `downloading` `done` `error-link` `error-platform` `error-network` `history` |
| `lang`  | `vi` (default) `en` |

Examples: `v2.html?state=result&lang=en`, `index.html#v=v3&d=desktop&l=vi&state=history` (index hash params: `v`, `d` = mobile/desktop, `l`, `state`).
Old names `error-invalid`, `error-unsupported`, `list` (and `?s=`) still work as aliases.

Every page also works by hand: **Dán/Paste** fills a fake link, **Kiểm tra link** analyses it, **Tải** runs a fake download
to **Lưu vào thiết bị**. Typing `hello` shows the link error, `https://example.com/x` the platform error, and any link containing
`offline` the network error. Add `?demo` to a variant page to show a small state switcher.

## Embedding

```html
<!-- phone -->
<iframe src="prototype/v1.html?state=result&lang=vi" width="375" height="760" style="border:0" title="Vidrop V1"></iframe>
<!-- desktop (render at 1280 and scale with CSS if the slot is narrower) -->
<iframe src="prototype/v1.html?state=result&lang=vi" width="1280" height="800" style="border:0" title="Vidrop V1"></iframe>
```

A variant page posts `{vidropState: "<state>"}` to `window.parent` whenever its state changes (`index.html` uses this to keep
the state buttons in sync).

## Images

Mobile = full page at 375 px; desktop = 1280×800 viewport; both @2x. VI for every state, plus `_EN` for Empty and Result.
State names: Empty, Analyzing, Result, Downloading, Done, ErrorLink, ErrorPlatform, ErrorNetwork, History.

## Rebuild (optional)

`_src/*.html` are templates, `_src/shared.js` is the shared state/i18n script, `_src/fonts-*.css` the font-face rules.
`python3 _src/build.py` regenerates `prototype/*.html`. `_src/getfonts.py` re-downloads the fonts from Google Fonts.
`_src/old-fonts-unused/` holds an earlier font set that is no longer referenced and can be deleted.

## Notes

- V3 shrinks its hero once a link is present so the result stays above the fold at 1280×800 (differs from `design-explore/v3`).
- V1 and V2 are pixel-identical to their `design-explore/` originals (EN, 375 and 1280, all 9 states).
