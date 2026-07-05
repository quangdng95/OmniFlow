# Known Issues

## main.py / ui.py are out of sync

`main.py` imports several color constants and references several widget/attribute names from `ui.py` that do not exist in the current `ui.py`:

- Colors imported but not defined in `ui.py`: `COLOR_ORANGE`, `COLOR_BLUE`, `COLOR_BTN_HOVER`, `COLOR_TEXT`, `COLOR_PURPLE`, `COLOR_FB`, `COLOR_REDNOTE`
- Widget/attribute names used in `main.py` but not defined in `ui.py`: `app.progress_bar` (actual: `self.progressbar`), `app.tabview`, `app.switch_notify`, `app.path_var`, `app.notify_var`

This means the app as checked in will not import/run as-is. Both files show `first commit` as their only git history, so this isn't a regression to bisect — it's the state of the repo.

Before making changes: check whether you're meant to reconcile `ui.py` to what `main.py` expects (or vice versa) — don't assume one file is authoritative without confirming with the user.

## main.py also lost its vendored yt-dlp binary

As of 2026-07-05 the vendored `./yt-dlp` executable was deleted (see `rules/running.md`) since `server.py` had stopped using it entirely — it only called the pip-installed `yt_dlp` package in-process since Round 7's speed work. `main.py`'s two `resource_path("yt-dlp")` calls will now fail to find that file too, on top of the `ui.py` mismatch above. Not fixed, since `main.py` already doesn't run and isn't being repaired — noted here so a future attempt to resurrect it knows about both problems, not just the first one it hits.
