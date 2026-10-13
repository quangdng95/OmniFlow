# First Launch & macOS Security Warnings

**🇬🇧 English&nbsp;&nbsp;|&nbsp;&nbsp;[🇻🇳 Tiếng Việt](FIRST_LAUNCH.vi.md)**

ViDrop isn't notarized by Apple (that requires a paid $99/year Apple Developer account), so
macOS shows a couple of one-time security prompts the first time you use it. Neither one means
anything is wrong — this guide walks through exactly what you'll see and what to click.

## 1. "ViDrop can't be opened because it is from an unidentified developer"

This appears the very first time you try to open the app after installing it.

**What to do:**

1. **Don't** double-click the app icon in `Applications` — that triggers the block again.
2. Instead, **right-click** (or Control-click) **ViDrop** in `Applications` and choose **Open**
   from the menu.
3. A dialog appears asking "Are you sure you want to open it?" — click **Open**.

That's it. macOS remembers this choice, so you'll never see this warning again for this specific
version of the app.

**Alternative method**, if right-click → Open doesn't show an Open button:

1. Try double-clicking the app once (it will still be blocked).
2. Open **System Settings → Privacy & Security**.
3. Scroll down — you'll see a message like *"ViDrop was blocked to protect your Mac"* with an
   **Open Anyway** button. Click it, then confirm in the dialog that follows.

> **Why does this happen?** macOS's Gatekeeper only trusts apps that are notarized by Apple or
> signed with a paid Developer ID. ViDrop is signed "ad-hoc" (a free, local-only signature) so
> it can be freely distributed without a developer account — but that also means Gatekeeper
> doesn't recognize it as a "known" app on first launch. This is a standard step for any small,
> independently distributed macOS app, not a red flag.

## 2. "ViDrop wants to use your confidential information stored in 'Chrome Safe Storage' in your keychain"

This one is **not required** to use ViDrop — it only appears when you check or download a link
from **Instagram**, **Threads** or **RedNote** (and only if you're logged into one of those in a
browser on this Mac: Chrome, Brave, Edge, Vivaldi, Opera, or Safari), or when you turn on
**Settings → YouTube sign-in**.

**What it's asking:** to download private or login-gated Instagram/Threads content (a Reel from
an account you follow, a Story, a private post), ViDrop needs to reuse your *own* logged-in
browser session — the same way your browser already trusts you. To do that, it needs to read one
encrypted value macOS stores for your browser ("Chrome Safe Storage" is the name Chrome/Brave/Edge
all use for this, even though the exact dialog wording varies slightly by browser).

**What to click:** **Always Allow** is recommended — this lets Instagram/Threads downloads work
without asking again. If you click **Allow** (single-use) or **Deny**:

- **Allow (once):** works for that one download, but you may see the prompt again next time.
- **Deny:** ViDrop simply won't be able to read that browser's session — Instagram,
  Threads and RedNote downloads that need a login will fail with a "no session found" message, but
  every other platform (TikTok, Facebook, LinkedIn, X, and YouTube unless you turned on YouTube
  sign-in) is completely unaffected.

**Everything stays on your Mac.** This permission only lets ViDrop read the session token
locally, on your own machine, to make a request to Instagram/Threads on your behalf — nothing is
ever sent anywhere else. See [Privacy](../README.md#privacy) in the main README.

> **Why might this prompt reappear after updating the app?** (It also appears again when you
> move from the old OmniFlow-era app, because macOS sees ViDrop as a new app.) Each new version of ViDrop you
> download is signed independently (see the Gatekeeper explanation above), and macOS Keychain
> ties this specific permission to the *exact* app version that asked for it. That means updating
> to a newer ViDrop release can trigger this prompt again even if you already clicked "Always
> Allow" for a previous version — this is expected macOS behavior, not a bug, and clicking
> **Always Allow** again resolves it the same way.

## 3. Moving from the old app (OmniFlow)

ViDrop is a separate app with its own name, icon and data folder, so nothing is replaced.

- **Your settings are copied once.** The first time you open ViDrop, it copies the old app's
  settings (download folder, playlist limit and so on) into `~/Library/Application Support/ViDrop`.
  The old folder, `~/Library/Application Support/OmniFlow`, is left exactly as it was.
- **History starts empty.** The old Mac app never kept its History after you closed it, so there is
  nothing to bring over. ViDrop keeps History and your language choice from now on.
- **macOS asks for permissions again** (Keychain, above), because it sees a new app.
- **When you're happy with ViDrop,** you can delete the old app and, if you like, the old folder.
  ViDrop doesn't touch either.

## Still stuck?

If ViDrop opens but check/download itself isn't working, that's a different issue — see
[Troubleshooting Check/Download Failures](TROUBLESHOOTING.md) instead.
