# Web App (primary, current)

As of 2026-07-03 the primary implementation is a Flask JSON API (`server.py`) + a React/TypeScript/Ant Design frontend (`frontend/`, built with Vite), wrapped in `pywebview` for a native macOS window. This superseded the Tkinter app (`main.py`/`ui.py`) as the maintained entry point — see `rules/known-issues.md` for why. **Only this implementation is updated going forward** (per explicit direction from the project owner as of 2026-07-03) — the legacy Tkinter app is not touched, and there is no longer a plain-HTML/JS `web/` frontend (replaced outright by `frontend/`, not incrementally migrated).

## Why React + Ant Design, not shadcn/ui

This frontend must pixel-match an existing Figma file (`_Quang-Information`, node `2420:22088`) whose design system is Ant Design — confirmed via Figma's own Code Connect component descriptions, which resolve every UI element (Button, Input, Segmented, Tag, Checkbox, Radio, Divider, Progress) to real `antd` imports. `~/.claude/CLAUDE.md`'s global "shadcn/ui only" rule does not apply here — see the override note at the top of this repo's `CLAUDE.md`. Tailwind is intentionally **not** used either — Ant Design has its own theme/token system (`ConfigProvider` in `frontend/src/theme.ts`), and layering Tailwind on top would fight it. Icons come from `@ant-design/icons` (the official Ant Design companion package, not a generic icon library) plus the repo's existing platform-tag SVGs (`Assets/Tags/*.svg`, copied into `frontend/src/assets/tags/`) — `lucide-react` is not used per explicit instruction.

## Running

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cd frontend && npm install
```

**Dev mode** (hot reload, two processes):
```bash
python3 server.py            # backend on :5001
cd frontend && npm run dev   # frontend on :5173, proxies /api/* to :5001 (see vite.config.ts)
```
Open `http://localhost:5173` in dev mode, not 5001 — the Flask dev server on 5001 has no built frontend to serve until you run `npm run build`.

**Production-like / desktop app** (single port, what `desktop_app.py` and end users actually use):
```bash
cd frontend && npm run build   # outputs to frontend/dist/
cd .. && python3 server.py     # serves frontend/dist/ at :5001
# or: python3 desktop_app.py   # native macOS window, same served build
```
`server.py`'s Flask `static_folder` points at `frontend/dist` — if you change frontend code and only see the old UI, you forgot to `npm run build` first (there's no auto-rebuild wired into `server.py`).

Port 5001 is hardcoded in both `server.py` (`PORT` env var, default 5001) and `desktop_app.py` (`PORT = 5001`) — if you change one, change the other.

## Architecture

- **`server.py`** — Flask app, single file, pure JSON API + static file serving. Standalone reimplementations of the old `main.py` helpers (`sanitize_filename`, `get_unique_filename`, `get_platform_info`, `get_ffmpeg_path`, `load_session`/`save_session`) — not imported from `main.py`, since `main.py` doesn't import cleanly (see `rules/known-issues.md`). Routes:
  - `POST /api/check` — runs yt-dlp in-process (`extract_video_info`) to return title/thumbnail/uploader/platform/available qualities/formatted `duration` (`MM:SS`). Rejects Instagram URLs outright for remote requests (see dual-mode section below).
  - `POST /api/download` — validates ffmpeg is available, then spawns a background `threading.Thread` running the real yt-dlp download, tracked in the module-level `jobs` dict keyed by a `uuid4` job id. Save location depends on local vs. remote (see below). Also rejects Instagram for remote requests.
  - `GET /api/progress/<job_id>` — polled by the frontend every 700ms; reports `status` (`running`/`done`/`cancelled`/`error`), `percent`, `text`, `filename`.
  - `GET /api/download-file/<job_id>` — remote-only; streams a finished job's file to the browser as a real attachment download and deletes the temp file/dir afterward.
  - `POST /api/cancel/<job_id>` — cancels the job via a `DownloadCancelled` raised from inside yt-dlp's progress hook.
  - `GET/POST /api/settings` — reads/writes `config.json` (`path`, `cookies_path`), plus a derived `cookies_status`. Local-only in effect, since only the local machine owner can reach the routes that populate it.
  - `POST /api/browse` / `POST /api/browse-file` — native macOS pickers via `osascript`; local-only, guarded server-side (see below).
  - `POST /api/open-folder` — shells out to `open <path>`; local-only, guarded server-side.
  - `GET /api/clipboard` — reads the pasteboard via `pbpaste`; local-only, guarded server-side.
- **`frontend/`** — Vite + React 19 + TypeScript + `antd` v6 + `@ant-design/icons`. No Tailwind, no shadcn/ui (see override note above).
  - `src/theme.ts` — `antd` `ConfigProvider` theme tokens (colorPrimary `#0d9585`, header bg `#13493c`, Inter font) matching the Figma file's design tokens exactly.
  - `src/api.ts` / `src/types.ts` — typed fetch wrappers over `server.py`'s routes.
  - `src/isLocal.ts` — `isLocal()`, the frontend half of the local/remote split (see below).
  - `src/components/` — one component per reusable Figma unit (`Header`, `Logo`, `PlatformTag`, `SectionCard`, `UrlInputCard`, `CheckingStatusCard`, `VideoInfoCard`, `QualityActionCard`, `DownloadProgressCard`, `DownloadSuccessCard`).
  - `src/pages/` — `HomePage` (the paste → check → quality/download → success flow, all client-side state, no routing library needed for 3 nav items), `SettingsPage`, `TermsPage`.
  - `src/App.tsx` — holds the single `page` state (`"home" | "settings" | "terms"`) and switches between pages; the three header nav buttons (`Home`/`Settings`/`Terms of Use`) call `onNavigate` to change it.
  - `vite.config.ts` — dev-only proxy of `/api` to `http://127.0.0.1:5001`.
- **`desktop_app.py`** — starts `server.py`'s Flask `app` in a background thread, then opens a `pywebview` window pointed at `http://127.0.0.1:5001`. Requires `frontend/dist` to already exist (run `npm run build` first). Always lands in the "local" branch of the dual-mode split below, since it navigates straight to the loopback address.

## Local vs. remote (dual-mode)

As of 2026-07-05, `server.py` can be exposed to other people (e.g. via an ngrok/Cloudflare Tunnel) without breaking the existing local/desktop-app experience — added because the app was originally single-user/single-machine only: native file dialogs render on the server's own screen, `pbpaste` reads the server's own clipboard, and downloads landed straight in a locally-configured folder, all of which are wrong for a remote visitor.

Detection is independent on each side, no shared state or session needed:
- Backend: `is_local_request()` checks the `Host` header's hostname against `{127.0.0.1, localhost, ::1}`. This is deliberately based on `request.host`, not `request.remote_addr` — a tunnel daemon forwards to `127.0.0.1` locally, so `remote_addr` would look local even for a genuinely remote visitor. A loopback *hostname*, on the other hand, is only reachable by a browser on the same machine, full stop.
- Frontend: `frontend/src/isLocal.ts`'s `isLocal()` checks `window.location.hostname` the same way.

What changes for a remote (non-local) request:
- `/api/browse`, `/api/browse-file`, `/api/open-folder`, `/api/clipboard` all return `403` — these only make sense when browser and server share a machine. The frontend's Paste button falls back to `navigator.clipboard.readText()` (the browser reading its own clipboard) instead of calling `/api/clipboard`.
- Instagram is rejected outright by `/api/check` and `/api/download` (`INSTAGRAM_LOCAL_ONLY_ERROR`) — **by design, not a TODO**. Instagram only works via a `cookies.txt` configured in Settings, and that config is one machine-wide file, not per-visitor. Letting Instagram through for remote requests would silently spend the local owner's own live Instagram session on a stranger's request. This was an explicit product decision, not a technical limitation to eventually lift — supporting it properly would require per-visitor cookie upload/storage/cleanup, which was deliberately scoped out.
- `/api/download` stages the file in a fresh `tempfile.mkdtemp(prefix="omniflow-")` directory instead of the configured Target Path folder. Once the job reaches `status: "done"`, the frontend links to `GET /api/download-file/<job_id>`, which streams the file as a real browser download and deletes the temp directory afterward (`flask.after_this_request`). The temp dir is also cleaned up on error/cancel. A visitor who never fetches the finished file (e.g. closes the tab) leaves an orphaned temp dir — accepted as a minor gap; there's no job-reaping infrastructure in this codebase.
- `SettingsPage`'s "Target Path" and "Instagram Cookies" sections are hidden entirely (the browser owns the download location for a remote visitor; Instagram isn't offered at all). Only "Language" remains.
- Remote clipboard reads via `navigator.clipboard.readText()` require a secure context (HTTPS or localhost) — if the app is tunnelled over plain HTTP, Paste won't work for remote visitors. This is a browser platform restriction, not something fixable in this app's code.

## Dependencies

Python: `flask`, `pywebview` (installed in `.venv`, since the system/Homebrew Python is externally managed and rejects global `pip install`). JS: `antd`, `@ant-design/icons`, `react`, `react-dom` (runtime) plus Vite/TypeScript tooling (dev) — see `frontend/package.json`. `frontend/node_modules` and `frontend/dist` are gitignored (Vite's own scaffolded `.gitignore`), so a fresh clone needs `npm install` + `npm run build` before `server.py` has anything to serve.
