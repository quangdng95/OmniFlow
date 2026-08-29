# Troubleshooting Check/Download Failures

**English** · [Tiếng Việt](TROUBLESHOOTING.vi.md)

If pasting a link into OmniFlow fails to check, or a download keeps failing, this guide walks
through the most common causes and the two built-in tools that make this diagnosable instead of a
guessing game.

If you haven't opened OmniFlow for the first time yet, or you're seeing a macOS security prompt
instead of an in-app error, see [First Launch & macOS Security Warnings](FIRST_LAUNCH.md) instead.

## Start here: the two Settings tools

Before anything else, know that Settings has two tools built for exactly this situation:

- **Diagnostic Logs** (Settings → Diagnostic Logs → **Open Log Folder**) — opens a folder
  containing `errors.log`, which records the *real*, technical reason behind a failure even when
  the app only shows you a short, friendly message. If you're reporting a bug, this file's
  contents are the single most useful thing you can attach.
- **Reset App Data** (Settings → Reset App Data → **Clear Cache & Reset Settings**) — clears
  OmniFlow's saved settings (download folder, saved login info) and starts fresh. This does **not**
  delete anything you've already downloaded. Use this when a failure doesn't make sense given
  what you know to be true (e.g. "I'm definitely logged into Instagram, but it says no session
  found") — a stale saved setting from a previous version is a common cause.

## Common messages and what they mean

OmniFlow's error messages are currently hardcoded in Vietnamese regardless of the app language you
have set in Settings (only the rest of the UI follows that setting) — so the exact text below is
what you'll actually see on screen. Each section quotes the real message alongside an English
explanation.

### Wrong build for your Mac's chip

> ❌ Lỗi: Bản OmniFlow này không tương thích với chip của máy Mac bạn đang dùng (kiến trúc ...).
> Vui lòng tải đúng bản dành cho máy bạn (OmniFlow-AppleSilicon.dmg hoặc OmniFlow-Intel.dmg) tại
> trang GitHub Releases của OmniFlow.

OmniFlow ships two separate builds — one native to Apple Silicon (M1/M2/M3/M4) and one native to
Intel — because the bundled `ffmpeg` tool only runs on the chip it was built for. This message
means you installed the wrong one for your Mac.

**Fix:** re-download from [the Download section of the README](../README.md#download) or
[Releases](https://github.com/quangdng95/OmniFlow/releases/latest), picking
**OmniFlow-AppleSilicon.dmg** for an M1/M2/M3/M4 Mac or **OmniFlow-Intel.dmg** for an Intel Mac.
Not sure which you have? Apple menu (top-left) → **About This Mac** — it names the chip directly.

### "Cannot download from a Private account"

> ❌ Lỗi: Không thể tải video từ tài khoản Private (Kín). OmniFlow hiện tại chỉ hỗ trợ tải nội
> dung Public (Công khai).

This message covers two different situations that OmniFlow can't always tell apart:

1. The account/post really is set to Private, and you don't follow it from a logged-in session on
   this Mac — this is expected; OmniFlow only reaches what your own logged-in account can see.
2. Your saved Instagram/Threads login session has gone stale or expired — the platform's response
   looks the same either way, so OmniFlow can't always distinguish "genuinely private" from
   "your session died."

**Try this:** open the link in your browser first — if you can see it there without being asked to
log in, it's public, and you're most likely hitting case 2. Try **Reset App Data**, then retry
the link. If you're still logged into Instagram/Threads in your browser, OmniFlow will pick up a
fresh session automatically on the next attempt.

### "No Instagram/Threads session found"

> ❌ Lỗi: Không tìm thấy phiên đăng nhập Instagram nào trên trình duyệt của máy này. Vui lòng
> đăng nhập Instagram trên Chrome/Safari/Brave (hoặc thêm cookies.txt thủ công trong Settings) rồi
> thử lại.
>
> *(Threads: ❌ Lỗi: Cần một trình duyệt đã đăng nhập Threads (threads.com) trên máy này để tải
> bài viết. Vui lòng đăng nhập rồi thử lại.)*

OmniFlow looks for a logged-in Instagram or Threads session in your local browsers (Chrome,
Brave, Edge, Vivaldi, Opera, Safari) automatically — you never need to export cookies by hand.
This message means it didn't find one. Make sure:

- You're actually logged into Instagram or Threads in one of those browsers on **this** Mac.
- You clicked **Allow** or **Always Allow** on the Keychain permission prompt — see
  [First Launch & macOS Security Warnings](FIRST_LAUNCH.md#2-omniflow-wants-to-use-your-confidential-information-stored-in-chrome-safe-storage-in-your-keychain)
  if you're not sure what that was.

Safari's cookies are protected by macOS in a way OmniFlow currently can't read at all (a
system-level restriction, not something OmniFlow can bypass) — if Safari is your only browser
with an Instagram/Threads login, use Chrome, Brave, or Edge instead for those platforms.

### "Unable to connect / network error"

> ❌ Lỗi: Không thể kết nối mạng để xử lý liên kết này. Vui lòng kiểm tra kết nối Internet (hoặc
> tường lửa/VPN) rồi thử lại.

OmniFlow couldn't reach the internet to process the link. Check your Wi-Fi/Ethernet connection,
and if you're on a VPN or a restrictive firewall, try temporarily disabling it — some corporate or
school networks block the platforms OmniFlow talks to.

### "Your IP is temporarily blocked/limited by this platform"

> ❌ Lỗi: IP của bạn đang tạm thời bị nền tảng này chặn/giới hạn. Vui lòng thử lại sau ít phút
> hoặc đổi mạng.

Some platforms (TikTok especially) rate-limit or temporarily block an IP address that makes too
many requests in a short time. Wait a few minutes and try again, or switch networks (e.g. mobile
hotspot) if it persists.

### "This LinkedIn document/slide-deck post isn't supported"

> ❌ Lỗi: Bài đăng LinkedIn dạng tài liệu/slide (PDF) hiện chưa được OmniFlow hỗ trợ tải. OmniFlow
> hiện chỉ hỗ trợ bài đăng LinkedIn dạng video hoặc ảnh.

LinkedIn has three different post types: video, image, and native document/slide-deck (PDF)
posts. OmniFlow supports the first two; the third has no known way to extract yet. This message
means the link you pasted is specifically that third, unsupported type — it's not a bug, just a
gap that's still open (see the [Roadmap](../README.md#roadmap) in the main README). If you have a
public example of this post type, opening a GitHub Issue with the link would help move this
forward.

### A generic "couldn't process this link" message

> ❌ Lỗi: Không thể xử lý liên kết này. Vui lòng kiểm tra lại link hoặc thử lại sau.

This is OmniFlow's fallback for an error it doesn't have a specific, friendly explanation for.
This is exactly what `errors.log` is for — open **Settings → Diagnostic Logs → Open Log Folder**,
open `errors.log`, and look for the most recent entry (they're timestamped). If you're reporting
this as a bug, include that entry's full text.

## Still not working?

1. Try **Reset App Data** once (Settings), then retry the link.
2. Quit and reopen OmniFlow.
3. Check `errors.log` (Settings → Diagnostic Logs) for the specific error.
4. If none of that resolves it, open a
   [GitHub Issue](https://github.com/quangdng95/OmniFlow/issues) with the link (if not
   private/sensitive), your Mac's chip and macOS version, and the relevant `errors.log` entry —
   see [Support & Issues](../README.md#support--issues) in the main README.
