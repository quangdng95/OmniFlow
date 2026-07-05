# Manual Test URLs

Real, known-good URLs given directly by the project owner (2026-07-05) for manually exercising `/api/check` and `/api/download` end-to-end against the live server whenever extraction/download logic in `server.py` changes. Use these — not synthetic or made-up IDs — whenever a round of work touches a specific platform's extraction, error handling, or thumbnail/format resolution; re-run the platform(s) affected before declaring the fix done.

- **RedNote**: `https://www.rednote.com/explore/67a85ba8000000001800862d?xsec_token=ABkDiv8mSEMTaBa4xCghCWIlsdwWdhOGTkGvm4-yPUmRA=&xsec_source=pc_search&source=web_explore_feed`
- **Facebook**: `https://www.facebook.com/reel/2194732404711942`
- **Instagram 1**: `https://www.instagram.com/reel/DUvAWWREkNIWX8YfDy9wqHG-5QRikFl5Rwixbk0/`
- **Instagram 2**: `https://www.instagram.com/p/DYTRs5Loe6A/`
- **TikTok**: `https://www.tiktok.com/@vio_decor127/video/7650834126223805717?is_from_webapp=1&sender_device=pc`

These are real, specific posts owned/found by the project owner, not stable yt-dlp test-suite fixtures — they can go private, get deleted, or have their CDN links expire over time. If one of these starts failing where it didn't before, check whether the post itself is still up/public before assuming it's a regression in this repo's code.

The two Instagram URLs will only succeed through `/api/check` or `/api/download` if a valid `cookies.txt` (containing a live `sessionid` for `instagram.com`) is configured in Settings — see `rules/web-app.md` and `session.md`'s Round 8/9 entries for why. Testing them with no cookies configured is expected to fail with the "requires a logged-in session" message; that is not a bug.
