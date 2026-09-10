# Remote Web Cloud (Linux) Portability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing `remote_web/` package run correctly on a Linux cloud VPS (Oracle Cloud Always Free) in addition to macOS, with a new manual-cookies-upload path for Instagram/Threads since a headless VPS has no browser/Keychain to auto-extract from.

**Architecture:** Two small, additive changes inside `remote_web/` — an OS branch in `ffmpeg_locator.py`, and a new file-upload route in `routes/settings.py` reusing `backend.config`'s existing (unmodified) `cookies_path`/`save_session` mechanism — plus a new frontend section and a deployment doc. Zero changes to `backend/`; every existing macOS code path and test stays unchanged.

**Tech Stack:** Same as the rest of `remote_web/` — Python 3 + Flask, React 19 + TypeScript + shadcn/ui (frontend). No new dependencies.

**Spec:** [docs/superpowers/specs/2026-08-30-remote-web-cloud-portability-design.md](../specs/2026-08-30-remote-web-cloud-portability-design.md)

## Global Constraints

- Zero changes to `backend/`, `server.py`, `desktop_app.py`, `OmniFlow.spec` — same constraint as every prior `remote_web/` task.
- Every existing macOS-path test in `remote_web/tests/test_ffmpeg_locator.py` must keep passing unmodified — the Linux branch is additive, not a replacement.
- The uploaded cookies file is a live credential — write it with `0600` permissions and gitignore it, matching `config.STATE_FILE`'s existing precedent.
- The new frontend section must be gated `!isLocal()` (shown only in remote mode) — it's a genuinely new, remote-only capability, not un-hiding the native app's old local-only Cookies field.
- Reuse `backend.config.get_cookies_path()`, `cookies_status_for()`, `save_session()`, `load_session()` unmodified — never re-implement cookie-status logic.

---

### Task 1: `ffmpeg_locator.py` — Linux support

**Files:**
- Modify: `remote_web/ffmpeg_locator.py`
- Modify: `remote_web/tests/test_ffmpeg_locator.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `resolve_ffmpeg_binary()` and `ffmpeg_unavailable_message()` keep their existing signatures (no args) and return types (`str | None`, `str`) — callers in `remote_web/app.py` and `remote_web/routes/health.py` need no changes.

- [ ] **Step 1: Write the failing tests**

Append to `remote_web/tests/test_ffmpeg_locator.py`:

```python
def test_resolve_ffmpeg_binary_uses_shutil_which_on_linux(monkeypatch):
    monkeypatch.setattr(ffmpeg_locator.platform, "system", lambda: "Linux")
    monkeypatch.setattr(ffmpeg_locator.shutil, "which", lambda name: "/usr/bin/ffmpeg" if name == "ffmpeg" else None)
    assert ffmpeg_locator.resolve_ffmpeg_binary() == "/usr/bin/ffmpeg"


def test_resolve_ffmpeg_binary_returns_none_on_linux_when_not_on_path(monkeypatch):
    monkeypatch.setattr(ffmpeg_locator.platform, "system", lambda: "Linux")
    monkeypatch.setattr(ffmpeg_locator.shutil, "which", lambda name: None)
    assert ffmpeg_locator.resolve_ffmpeg_binary() is None


def test_resolve_ffmpeg_binary_returns_none_on_an_unsupported_os(monkeypatch):
    monkeypatch.setattr(ffmpeg_locator.platform, "system", lambda: "Windows")
    assert ffmpeg_locator.resolve_ffmpeg_binary() is None


def test_ffmpeg_unavailable_message_on_linux_suggests_a_package_manager(monkeypatch):
    monkeypatch.setattr(ffmpeg_locator.platform, "system", lambda: "Linux")
    message = ffmpeg_locator.ffmpeg_unavailable_message()
    assert "apt install ffmpeg" in message
    assert "kiến trúc CPU" not in message  # the macOS-specific phrasing must not leak in
```

Also add this import line to the top of `remote_web/tests/test_ffmpeg_locator.py` (it doesn't currently import `shutil`, since only `subprocess` was ever monkeypatched):

```python
import shutil
```

(Keep the existing `import os` / `import subprocess` / `from remote_web import ffmpeg_locator` lines as they are.)

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest remote_web/tests/test_ffmpeg_locator.py -v`
Expected: the 4 new tests FAIL (`AttributeError` or assertion mismatch — `platform.system` isn't consulted yet, `shutil` isn't imported by `ffmpeg_locator.py` yet). The 5 pre-existing tests must still PASS unchanged (baseline, run before your edit to confirm — `git stash` the test file changes, run, `git stash pop` if you want to double-check in isolation, or just note the pre-edit `pytest -q` full-suite count from Task 0 context: 355 passed).

- [ ] **Step 3: Implement the Linux branch**

Replace the full contents of `remote_web/ffmpeg_locator.py` with:

```python
"""Architecture-aware ffmpeg binary resolution for remote_web's unfrozen
(non-PyInstaller) execution (spec §5.1 of the original design;
§2.1 of docs/superpowers/specs/2026-08-30-remote-web-cloud-portability-design.md
for the Linux branch added here).

backend.paths.get_ffmpeg_path() always looks for a file literally named
`ffmpeg` at the repo root - correct only because OmniFlow.spec already staged
the matching-architecture binary under that exact name at BUILD time.
remote_web runs unfrozen (`python3 -m remote_web.app`, no PyInstaller step),
so nothing performs that selection - this module does its own resolution
instead, entirely inside remote_web/, and never calls
backend.paths.get_ffmpeg_path().

Two platforms are supported:
- macOS (Darwin): the vendored, Git-LFS-tracked binaries at the repo root -
  ./ffmpeg (arm64) and ./ffmpeg-x86_64 (Intel), picked by platform.machine().
- Linux: no vendoring at all - a cloud VPS deployment installs ffmpeg via its
  system package manager (`apt install ffmpeg`), which puts a working binary
  on PATH. remote_web always runs from a source checkout on Linux too (never
  frozen), so there is nothing to bundle; shutil.which("ffmpeg") is the
  correct, idiomatic way to depend on a system package here.
Any other platform.system() value returns None explicitly, rather than
falling through to either branch.
"""

import os
import platform
import shutil
import subprocess

from backend import paths

_BAD_CPU_TYPE_ERRNO = 86


def _exec_ok(path):
    try:
        subprocess.run([path, "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def resolve_ffmpeg_binary():
    system = platform.system()
    if system == "Linux":
        return shutil.which("ffmpeg")
    if system != "Darwin":
        return None

    name = "ffmpeg" if platform.machine() == "arm64" else "ffmpeg-x86_64"
    candidate = os.path.join(paths.BASE_DIR, name)
    if not os.path.exists(candidate):
        return None
    if not os.access(candidate, os.X_OK):
        try:
            os.chmod(candidate, 0o755)
        except OSError:
            pass
    if not os.access(candidate, os.X_OK):
        return None
    if not _exec_ok(candidate):
        return None
    return candidate


def ffmpeg_unavailable_message():
    # Unlike backend.paths.ffmpeg_unavailable_message() (which tells an END
    # USER which .dmg to download instead), remote_web is one long-running
    # deployment on one machine - an unresolvable ffmpeg here means the
    # DEPLOYMENT itself is broken, not that the visitor picked the wrong
    # installer. The actionable audience is whoever runs the machine, not
    # the phone on the other end.
    if platform.system() == "Linux":
        return (
            "❌ Lỗi: Không tìm thấy FFmpeg khả dụng trên máy chủ này. "
            "Vui lòng cài đặt qua trình quản lý gói của hệ điều hành "
            "(vd: apt install ffmpeg) rồi khởi động lại dịch vụ."
        )
    return (
        "❌ Lỗi: Không tìm thấy FFmpeg khả dụng cho kiến trúc CPU của máy chủ này "
        f"({platform.machine()}). Vui lòng liên hệ quản trị viên để kiểm tra lại triển khai."
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest remote_web/tests/test_ffmpeg_locator.py -v`
Expected: PASS (9 tests total — 5 pre-existing macOS tests + 4 new Linux/unsupported-OS tests).

- [ ] **Step 5: Run the full repo suite to confirm nothing else broke**

Run: `pytest -q`
Expected: PASS, 4 more than the pre-task baseline (355 + 4 = 359).

- [ ] **Step 6: Commit**

```bash
git add remote_web/ffmpeg_locator.py remote_web/tests/test_ffmpeg_locator.py
git commit -m "remote_web: add Linux ffmpeg resolution via PATH (cloud portability)"
```

---

### Task 2: `routes/settings.py` — manual cookies.txt upload endpoint

**Files:**
- Modify: `remote_web/routes/settings.py`
- Modify: `remote_web/tests/test_settings_routes.py`
- Modify: `.gitignore` (repo root)

**Interfaces:**
- Consumes: `backend.config.save_session`, `load_session`, `cookies_status_for` (existing, unmodified); `remote_web.config.STATE_FILE` (existing, Task 1 of the original remote-web-access plan — used only to colocate the new cookies file, same pattern `_get_settings_file()` already uses for `settings.json`).
- Produces: `POST /api/settings/cookies` on the existing `bp` blueprint (already mounted in `remote_web/app.py` — no registration change needed). `GET /api/settings` gains a new `cookies_status` field in its response (existing consumers that ignore unknown JSON fields are unaffected).

- [ ] **Step 1: Write the failing tests**

Append to `remote_web/tests/test_settings_routes.py` (the existing file already has a `client`/`isolated_state_file` fixture pattern from Task 8 of the original plan — reuse it):

```python
# ---- POST /api/settings/cookies ----

import io

NETSCAPE_COOKIE_LINE = ".instagram.com\tTRUE\t/\tTRUE\t1999999999\tsessionid\tabc123\n"


def test_upload_cookies_requires_trust(client):
    remote_app.config["TESTING"] = True
    anon_client = remote_app.test_client()
    resp = anon_client.post(
        "/api/settings/cookies",
        data={"cookies": (io.BytesIO(NETSCAPE_COOKIE_LINE.encode()), "cookies.txt")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 401


def test_upload_cookies_saves_file_and_wires_into_backend_config(client, tmp_path, monkeypatch):
    _unlock(client)
    cookies_file_path = tmp_path / "remote_web_cookies.txt"
    monkeypatch.setattr("remote_web.routes.settings._COOKIES_FILE", str(cookies_file_path))

    resp = client.post(
        "/api/settings/cookies",
        data={"cookies": (io.BytesIO(NETSCAPE_COOKIE_LINE.encode()), "cookies.txt")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["cookies_status"] == "valid"

    assert cookies_file_path.exists()
    assert cookies_file_path.read_text() == NETSCAPE_COOKIE_LINE
    assert oct(cookies_file_path.stat().st_mode)[-3:] == "600"

    session = backend_config.load_session()
    assert session["cookies_path"] == str(cookies_file_path)


def test_upload_cookies_rejects_missing_file(client):
    _unlock(client)
    resp = client.post("/api/settings/cookies", data={}, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_upload_cookies_rejects_empty_file(client):
    _unlock(client)
    resp = client.post(
        "/api/settings/cookies",
        data={"cookies": (io.BytesIO(b""), "cookies.txt")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400


def test_upload_cookies_rejects_oversized_file(client):
    _unlock(client)
    too_big = b"x" * (64 * 1024 + 1)
    resp = client.post(
        "/api/settings/cookies",
        data={"cookies": (io.BytesIO(too_big), "cookies.txt")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400


def test_get_settings_reports_cookies_status(client, tmp_path, monkeypatch):
    _unlock(client)
    cookies_file_path = tmp_path / "remote_web_cookies.txt"
    monkeypatch.setattr("remote_web.routes.settings._COOKIES_FILE", str(cookies_file_path))
    client.post(
        "/api/settings/cookies",
        data={"cookies": (io.BytesIO(NETSCAPE_COOKIE_LINE.encode()), "cookies.txt")},
        content_type="multipart/form-data",
    )
    resp = client.get("/api/settings")
    assert resp.get_json()["cookies_status"] == "valid"
```

Add these imports at the top of `remote_web/tests/test_settings_routes.py` if not already present (check the existing file first — it already imports `backend_config`, `config`, `remote_app`, and has a `_unlock(client)` helper and `client` fixture from Task 8; only add what's missing):

```python
import io
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest remote_web/tests/test_settings_routes.py -v`
Expected: FAIL — `404 NOT FOUND` for the new route (doesn't exist yet), and `KeyError: 'cookies_status'` for the last test.

- [ ] **Step 3: Implement the upload endpoint**

Replace the full contents of `remote_web/routes/settings.py` with:

```python
"""GET/POST /api/settings, POST /api/settings/cookies.

Three very different kinds of state live behind these routes:
- `language` is remote_web's own concern, in its own small file next to
  config.STATE_FILE - in practice the frontend's actual language switch
  reads/writes localStorage directly (LanguageContext.tsx), never this
  route, but the field is kept for API-shape parity with the native app and
  in case a future frontend change starts using it.
- `playlist_limit` is deliberately proxied straight through to
  backend.config's own session file (reused unmodified) - the frontend's
  Playlist Limit control is NOT gated behind isLocal() the way Target
  Path/Cookies are (it's a real, unhidden control in remote mode), and
  backend.extraction.extract_video_info already reads playlist_limit from
  backend.config.load_session() internally, so proxying it here is what
  makes changing it from the phone actually affect real playlist
  extraction - keeping a wholly separate copy would silently do nothing.
- `cookies_path`/`cookies_status` (new, spec:
  docs/superpowers/specs/2026-08-30-remote-web-cloud-portability-design.md
  §2.2): a headless Linux cloud deployment has no browser/Keychain to
  auto-extract Instagram/Threads cookies from the way the native app does,
  so this exposes a manual cookies.txt upload instead. The uploaded file is
  wired into backend.config's EXISTING cookies_path mechanism (reused
  unmodified) - backend.cookies.instagram_cookiefile_candidates() and every
  Instagram/Threads resolver in remote_web/routes/media.py already consult
  backend.config.get_cookies_path() first, so nothing else needs to change
  for an uploaded cookies file to actually take effect.

`path`/`browser` are deliberately NOT part of this response at all - the
frontend never reads or writes them in remote mode (that section is hidden
behind isLocal(), see frontend/src/pages/SettingsPage.tsx).
"""

import json
import os

from flask import Blueprint, jsonify, request

from backend import config as backend_config
from remote_web import config

bp = Blueprint("settings", __name__)

_DEFAULT_LANGUAGE = "en"
# Deliberately NOT under config.TEMP_ROOT - reaper.py's mtime-based sweep
# (original design spec §5.4) must never treat this as an orphaned job
# directory and delete a live credential.
_COOKIES_FILE = os.path.join(os.path.dirname(config.STATE_FILE), ".manual_cookies.txt")
_MAX_COOKIES_FILE_BYTES = 64 * 1024


def _get_settings_file():
    """Compute dynamically so monkeypatched config.STATE_FILE is used in tests."""
    return os.path.join(os.path.dirname(config.STATE_FILE), "settings.json")


def _load_language():
    settings_file = _get_settings_file()
    if not os.path.exists(settings_file):
        return _DEFAULT_LANGUAGE
    try:
        with open(settings_file, "r") as f:
            return json.load(f).get("language", _DEFAULT_LANGUAGE)
    except (OSError, json.JSONDecodeError):
        return _DEFAULT_LANGUAGE


def _save_language(language):
    settings_file = _get_settings_file()
    os.makedirs(os.path.dirname(settings_file), exist_ok=True)
    with open(settings_file, "w") as f:
        json.dump({"language": language}, f)


@bp.get("/api/settings")
def get_settings():
    session = backend_config.load_session()
    return jsonify({
        "language": _load_language(),
        "playlist_limit": session["playlist_limit"],
        "cookies_status": backend_config.cookies_status_for(session["cookies_path"]),
    })


@bp.post("/api/settings")
def update_settings():
    data = request.get_json(force=True) or {}
    language = data.get("language", _load_language())
    _save_language(language)

    session = backend_config.load_session()
    playlist_limit = data.get("playlist_limit", session["playlist_limit"])
    if playlist_limit != session["playlist_limit"]:
        backend_config.save_session(session["path"], session["cookies_path"], session["browser"], playlist_limit)

    return jsonify({"language": language, "playlist_limit": playlist_limit})


@bp.post("/api/settings/cookies")
def upload_cookies():
    uploaded = request.files.get("cookies")
    if uploaded is None or uploaded.filename == "":
        return jsonify({"error": "No file uploaded"}), 400

    body = uploaded.read(_MAX_COOKIES_FILE_BYTES + 1)
    if not body:
        return jsonify({"error": "Uploaded file is empty"}), 400
    if len(body) > _MAX_COOKIES_FILE_BYTES:
        return jsonify({"error": "Uploaded file is too large (max 64 KiB) - this doesn't look like a real cookies.txt"}), 400

    os.makedirs(os.path.dirname(_COOKIES_FILE), exist_ok=True)
    with open(_COOKIES_FILE, "wb") as f:
        f.write(body)
    # This is a live session credential, same care as config.STATE_FILE.
    os.chmod(_COOKIES_FILE, 0o600)

    session = backend_config.load_session()
    backend_config.save_session(session["path"], _COOKIES_FILE, session["browser"], session["playlist_limit"])

    return jsonify({"cookies_status": backend_config.cookies_status_for(_COOKIES_FILE)})
```

- [ ] **Step 4: Add the new cookies file to `.gitignore`**

Open the repo-root `.gitignore` and extend the existing `remote_web/`-owned entries:

```
# remote_web's own runtime state - trust token/secret key, its own language
# settings file, a manually-uploaded Instagram/Threads cookies.txt (cloud
# portability, docs/superpowers/specs/2026-08-30-remote-web-cloud-portability-design.md),
# and job temp dirs, never committed
remote_web/.state.json
remote_web/settings.json
remote_web/.manual_cookies.txt
remote_web/.tmp/
```

(Only add the `remote_web/.manual_cookies.txt` line if `.state.json`/`settings.json`/`.tmp/` are already present from earlier tasks — check the file first rather than duplicating.)

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest remote_web/tests/test_settings_routes.py -v`
Expected: PASS (12 tests total — 6 pre-existing + 6 new).

- [ ] **Step 6: Run the full repo suite**

Run: `pytest -q`
Expected: PASS, 359 + 6 = 365.

- [ ] **Step 7: Commit**

```bash
git add remote_web/routes/settings.py remote_web/tests/test_settings_routes.py .gitignore
git commit -m "remote_web: add manual cookies.txt upload for headless/cloud deployments"
```

---

### Task 3: Frontend — remote-only cookies upload section

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/i18n/translations.ts`
- Modify: `frontend/src/pages/SettingsPage.tsx`

**Interfaces:**
- Consumes: `CookiesStatus` (existing type, `frontend/src/types.ts:52`); Task 2's `POST /api/settings/cookies` (returns `{cookies_status: CookiesStatus}` or `{error: string}`) and `GET /api/settings` (now also returns `cookies_status`).
- Produces: `api.uploadCookies(file: File): Promise<{ cookies_status: CookiesStatus }>` — a new function on the existing `api` object in `frontend/src/api.ts`, following the same pattern every other `api.*` function already uses.

- [ ] **Step 1: Add the `uploadCookies` API function**

In `frontend/src/api.ts`, add this function to the exported `api` object (place it near `updateSettings`, since it's part of the same settings surface):

```typescript
  uploadCookies: async (file: File): Promise<{ cookies_status: CookiesStatus }> => {
    const formData = new FormData();
    formData.append("cookies", file);
    let res: Response;
    try {
      res = await fetch("/api/settings/cookies", { method: "POST", body: formData });
    } catch {
      throw new Error("Can't reach the OmniFlow server. Make sure it's running, then reload this page.");
    }
    let data;
    try {
      data = await res.json();
    } catch {
      throw new Error(`Request failed${res.ok ? "" : ` (${res.status})`}.`);
    }
    if (!res.ok) {
      throw new Error(data.error || "Upload failed");
    }
    return data as { cookies_status: CookiesStatus };
  },
```

This deliberately does NOT reuse the shared `request<T>()` helper — that helper always sets `Content-Type: application/json`, which is wrong for a `multipart/form-data` upload (the browser must set the `Content-Type` itself, including the multipart boundary, when a `FormData` body is used). The error-handling shape (non-JSON-response guard, `data.error` fallback) intentionally mirrors `request<T>()`'s own logic so upload failures degrade exactly as gracefully as every other API call's.

Add `CookiesStatus` to the existing type import line at the top of `frontend/src/api.ts` if it isn't already imported (check the current import line — `Settings` is already imported from `./types`, `CookiesStatus` may or may not be alongside it already since `browseFile` already returns one).

- [ ] **Step 2: Add the translations**

In `frontend/src/i18n/translations.ts`, add a new `cookiesUpload` section to all three places (the `Translations` interface, the `en` object, and the `vi` object) inside `settingsPage`, right after `targetPath` (before `language`) — matching where the native app's removed field used to sit:

Interface (add after `targetPath: { ... };` inside the `settingsPage:` block):

```typescript
    cookiesUpload: {
      heading: string;
      description: string;
      chooseFile: string;
      upload: string;
      statusValid: string;
      statusNoSession: string;
      statusNone: string;
      uploadedOk: string;
    };
```

`en` object (add after the `targetPath: { ... },` entry inside `settingsPage: {`):

```typescript
    cookiesUpload: {
      heading: "Instagram / Threads Cookies",
      description: "This deployment has no browser to auto-detect a login session from. Export a cookies.txt from a browser where you're logged into Instagram or Threads, and upload it here.",
      chooseFile: "Choose cookies.txt…",
      upload: "Upload",
      statusValid: "A working Instagram session was found in the uploaded file.",
      statusNoSession: "The uploaded file doesn't contain a valid Instagram session — export a fresh cookies.txt and try again.",
      statusNone: "No cookies file uploaded yet.",
      uploadedOk: "Cookies file uploaded.",
    },
```

`vi` object (add after the `targetPath: { ... },` entry inside `settingsPage: {`):

```typescript
    cookiesUpload: {
      heading: "Cookies Instagram / Threads",
      description: "Bản triển khai này không có trình duyệt để tự phát hiện phiên đăng nhập. Hãy xuất file cookies.txt từ trình duyệt đang đăng nhập Instagram hoặc Threads, rồi tải lên tại đây.",
      chooseFile: "Chọn file cookies.txt…",
      upload: "Tải lên",
      statusValid: "Đã tìm thấy phiên đăng nhập Instagram hợp lệ trong file vừa tải lên.",
      statusNoSession: "File vừa tải lên không chứa phiên đăng nhập Instagram hợp lệ — hãy xuất lại cookies.txt mới rồi thử lại.",
      statusNone: "Chưa có file cookies nào được tải lên.",
      uploadedOk: "Đã tải lên file cookies.",
    },
```

- [ ] **Step 3: Add the Settings page section**

In `frontend/src/pages/SettingsPage.tsx`:

1. Add state for the selected file and current cookies status, near the existing `path`/`rememberPath`/`playlistLimit` state declarations:

```typescript
  const [cookiesStatus, setCookiesStatus] = useState<CookiesStatus | null>(null);
  const [selectedCookiesFile, setSelectedCookiesFile] = useState<File | null>(null);
```

Add `CookiesStatus` to the existing `import type { Language } from "../i18n/translations";`-style type imports at the top of the file (import it from `"../types"`).

2. In the existing `useEffect` that calls `api.getSettings()` on mount, also capture the new field:

```typescript
    void api.getSettings().then((settings) => {
      setPath(settings.path);
      setPlaylistLimit(settings.playlist_limit ?? 100);
      setCookiesStatus(settings.cookies_status ?? null);
    });
```

3. Add a handler function, alongside the other `handle*` functions:

```typescript
  const handleUploadCookies = async () => {
    if (!selectedCookiesFile) return;
    try {
      const { cookies_status } = await api.uploadCookies(selectedCookiesFile);
      setCookiesStatus(cookies_status);
      setSelectedCookiesFile(null);
      toast.success(t.settingsPage.cookiesUpload.uploadedOk);
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const handleCookiesFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSelectedCookiesFile(e.target.files?.[0] ?? null);
  };
```

4. Add the new section's JSX, placed right after the closing `)}` of the existing `{isLocal() && ( <SectionCard> ... Target Path ... </SectionCard> )}` block, gated the opposite way (`!isLocal()`):

```tsx
          {!isLocal() && (
            <SectionCard className="p-5 bg-white border border-slate-200/50 shadow-sm rounded-xl flex flex-col gap-4">
              <p className="text-base font-semibold text-slate-800 m-0">
                {t.settingsPage.cookiesUpload.heading}
              </p>
              <p className="text-xs text-slate-500 font-normal m-0 leading-relaxed">
                {t.settingsPage.cookiesUpload.description}
              </p>
              <div className="flex flex-col sm:flex-row gap-2 w-full">
                <input
                  type="file"
                  accept=".txt"
                  onChange={handleCookiesFileChange}
                  className="flex-1 text-xs text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-slate-100 file:px-3 file:py-1.5 file:text-xs file:font-semibold"
                />
                <Button
                  onClick={handleUploadCookies}
                  disabled={!selectedCookiesFile}
                  className="w-fit bg-[#0d9585] text-white hover:bg-[#0d9585]/90"
                >
                  {t.settingsPage.cookiesUpload.upload}
                </Button>
              </div>
              <p className="text-xs text-slate-500 m-0">
                {cookiesStatus === "valid" && t.settingsPage.cookiesUpload.statusValid}
                {cookiesStatus === "no_session" && t.settingsPage.cookiesUpload.statusNoSession}
                {(cookiesStatus === "none" || cookiesStatus === null) && t.settingsPage.cookiesUpload.statusNone}
              </p>
            </SectionCard>
          )}
```

- [ ] **Step 4: Verify with lint and build**

Run: `cd frontend && npm run lint && npm run build && cd ..`
Expected: both succeed cleanly (same pre-existing warnings as before this task, no new errors).

- [ ] **Step 5: Run the existing frontend test suite**

Run: `cd frontend && npx vitest run && cd ..`
Expected: PASS, same count as before this task (no existing test exercises Settings' cookies section, since it didn't exist before — this step is a regression check, not new coverage).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types.ts frontend/src/api.ts frontend/src/i18n/translations.ts frontend/src/pages/SettingsPage.tsx
git commit -m "remote_web frontend: add remote-only Instagram/Threads cookies upload UI"
```

---

### Task 4: Deployment documentation + final verification

**Files:**
- Modify: `remote_web/README.md`
- No code changes — this task documents deployment and runs the plan's closing verification.

**Interfaces:**
- Consumes: nothing new — this task is documentation + verification only.

- [ ] **Step 1: Add a new section to `remote_web/README.md`**

Read the current file first, then add a new top-level section titled `## Alternative: free-tier cloud deployment (Linux)`, placed after the existing macOS setup section and before "Revoking access", containing:

```markdown
## Alternative: free-tier cloud deployment (Linux)

Everything above describes running `remote_web` on a dedicated Mac. The same
package also runs on a Linux VPS — useful if you'd rather not keep any Mac
powered on at all. This is a **separate, independent deployment**: it gets
its own hostname, its own trust token, and does not affect the Mac
deployment in any way if you're running both.

**Trade-off vs. the Mac deployment:** Instagram/Threads auth can't
auto-detect a browser session on a headless Linux box (no Keychain, no real
browser) — you upload a `cookies.txt` manually instead, via a new
Settings section that only appears when running in remote mode. Export one
from a browser where you're logged into Instagram/Threads (any cookie
export extension works), and upload it once after first unlocking the
cloud deployment; it'll need re-uploading whenever the session goes stale,
same as any exported cookies file eventually does.

1. Create an [Oracle Cloud](https://www.oracle.com/cloud/free/) account and
   provision an "Always Free" instance (an Ampere A1 / ARM shape, or an AMD
   Micro shape) running Ubuntu — this tier is free forever, not a
   time-limited trial. Note: sign-up requires a card for identity
   verification (you are not charged on the Always Free tier), and Oracle
   has been known to flag long-idle free accounts for review — check in on
   the instance occasionally.
2. `sudo apt update && sudo apt install -y python3-venv python3-pip nodejs npm ffmpeg`
   — `ffmpeg` here is the whole reason this deployment doesn't need any of
   the macOS vendored-binary machinery: a plain system package is enough.
3. Clone the repo, then the same setup as the Mac section above:
   ```bash
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   cd frontend && npm install && npm run build && cd ..
   ```
4. Install `cloudflared` for Linux (Cloudflare's `.deb` package or binary
   release), `cloudflared tunnel login` against the **same** Cloudflare
   account already used for the Mac's tunnel (one account can hold several
   independent tunnels), then create a second named tunnel and route a
   **different** hostname to it (e.g. `cloudflared tunnel route dns
   omniflow-cloud cloud.yourdomain.com`) — do not reuse the Mac deployment's
   hostname.
5. Two `systemd` units (the Linux equivalent of the Mac's two LaunchAgents
   — see `/etc/systemd/system/remote-web.service` and
   `cloudflared.service`), both `Restart=on-failure` and
   `WantedBy=multi-user.target`. Unlike the Mac's LaunchAgent (which needs
   Automatic Login to reach the login Keychain — see "Why a LaunchAgent,
   not a LaunchDaemon" above), a Linux VPS has no analogous GUI-session
   requirement at all: Instagram/Threads auth here is the manually-uploaded
   `cookies.txt`, not `browser_cookie3`, so a plain systemd service survives
   an unattended reboot with no special login configuration needed.
6. `python3 -m remote_web.config show` for this deployment's own token (it
   is independent from the Mac deployment's token — each `remote_web`
   process has its own `.state.json`). Visit
   `https://<your-cloud-hostname>/unlock`, unlock, then go to Settings and
   upload a `cookies.txt` if you need Instagram/Threads to work.

**Known, accepted trade-off:** a cloud provider's IP range is more likely to
be rate-limited or blocked by TikTok specifically than a residential IP
(confirmed by this repo's own live testing — see MISTAKES.md) — no
mitigation (e.g. a residential proxy) is built for this in v1. Every other
platform is unaffected.
```

- [ ] **Step 2: Add the cloud checklist items to the existing manual live checklist**

In the same file's existing `## Manual live checklist` section, add these items (append, don't replace the existing Mac-focused ones):

```markdown
- [ ] (Cloud deployment only) `GET /api/health/detail` on the cloud hostname reports `ffmpeg: true` (resolved via `apt`-installed ffmpeg, not a vendored binary).
- [ ] (Cloud deployment only) Settings shows the new cookies-upload section (only in remote mode); uploading a real `cookies.txt` flips its status to "valid".
- [ ] (Cloud deployment only) An Instagram or Threads check/download succeeds after uploading cookies.
- [ ] (Cloud deployment only) A plain YouTube check/download succeeds with no cookies uploaded at all (proves platforms that need no auth are unaffected by the whole cookies-upload feature being new).
```

- [ ] **Step 3: Run the full verification suite**

```bash
pytest -q                                    # expect 365 passed (359 + 6 from Task 2... already counted; confirm final number matches Task 1+2's running totals)
cd frontend && npm run lint && npm run build && npx vitest run && cd ..
git diff --stat HEAD -- backend/ server.py desktop_app.py OmniFlow.spec   # must be empty
```

- [ ] **Step 4: Commit**

```bash
git add remote_web/README.md
git commit -m "remote_web: document free-tier Linux cloud deployment (Oracle Cloud)"
```

---

## Self-Review

**Spec coverage:** §2.1 (ffmpeg Linux branch) → Task 1. §2.2 (cookies upload) → Task 2 (backend) + Task 3 (frontend). §3 (deployment steps) → Task 4. §4 (testing) → covered inline in Tasks 1-3's own test steps, plus Task 4's manual checklist additions. §5 (resolved open questions) → already reflected in the design choices throughout (direct install, Oracle Cloud, new domain, TikTok risk accepted — no task contradicts any of these).

**Placeholder scan:** no TBD/TODO; every code step is complete, runnable code, not a description.

**Type consistency:** `resolve_ffmpeg_binary() -> str | None` and `ffmpeg_unavailable_message() -> str` (Task 1) keep their pre-existing signatures, so `remote_web/app.py` and `remote_web/routes/health.py` (untouched by this plan) keep working unchanged. `POST /api/settings/cookies` response shape (`{"cookies_status": CookiesStatus}` on success, `{"error": str}` on failure — Task 2) matches exactly what Task 3's `api.uploadCookies` expects and unwraps. `GET /api/settings`'s new `cookies_status` field (Task 2) matches the `CookiesStatus` type already declared in `frontend/src/types.ts` and consumed by Task 3's `SettingsPage.tsx` state.
