# Troubleshooting Check/Download Failures

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

### "Cannot download from a Private account"

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

OmniFlow couldn't reach the internet to process the link. Check your Wi-Fi/Ethernet connection,
and if you're on a VPN or a restrictive firewall, try temporarily disabling it — some corporate or
school networks block the platforms OmniFlow talks to.

### "Your IP is temporarily blocked/limited by this platform"

Some platforms (TikTok especially) rate-limit or temporarily block an IP address that makes too
many requests in a short time. Wait a few minutes and try again, or switch networks (e.g. mobile
hotspot) if it persists.

### A generic "couldn't process this link" message

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
