# Running & Dependencies

Current (web app — see `rules/web-app.md` for full detail):

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..
python3 server.py        # browser: http://127.0.0.1:5001
python3 desktop_app.py   # native macOS window
```

The frontend (`frontend/`, React + TypeScript + Ant Design) must be built at least once (`npm run build`) before `server.py` has anything to serve — it has no auto-rebuild. For frontend iteration with hot reload, run `npm run dev` in `frontend/` instead (serves on :5173, proxies `/api` to the Flask server on :5001) — see `rules/web-app.md`.

Legacy (Tkinter — currently broken, see `rules/known-issues.md`):

```bash
python3 main.py
```

Tests: `pytest` (repo root, `.venv` active) for `server.py`/`tests/test_server.py`; `cd frontend && npm test` (vitest) for the frontend. No linter or build/packaging script in the repo. The system/Homebrew Python is externally managed (PEP 668) and rejects `pip install` outside a venv — always use `.venv`.

- `cairosvg` (only needed by the legacy Tkinter app) is optional: icon/logo/tag SVG rendering in `ui.py` (`load_assets`) is wrapped in `try/except Exception: pass`, so that app still runs without it, just without icons.
- `ffmpeg` is vendored as an executable at the repo root (`./ffmpeg`) and resolved via a `resource_path()` helper (present in both `main.py` and `server.py`), which also handles the PyInstaller-frozen (`sys._MEIPASS`) case for a packaged `.app` build. If the vendored `ffmpeg` is missing/non-executable, `get_ffmpeg_path()` falls back to `shutil.which("ffmpeg")`.
- `yt-dlp` used to also be vendored as an executable (`./yt-dlp`), resolved the same way via `resource_path()` in `main.py`. That binary was removed as of 2026-07-05 — `server.py` has called the pip-installed `yt_dlp` package in-process since the Round 7 speed work (see `rules/web-app.md`), so the vendored copy had been fully unused dead weight for several rounds before removal. `main.py`'s `resource_path("yt-dlp")` calls will now fail if that already-broken app (see `rules/known-issues.md`) is ever repaired.

## Git LFS

`ffmpeg` is tracked via Git LFS (`.gitattributes`: `ffmpeg filter=lfs diff=lfs merge=lfs -text`).
