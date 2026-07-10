# First Launch & macOS Security Warnings

OmniFlow isn't notarized by Apple (that requires a paid $99/year Apple Developer account), so
macOS shows a couple of one-time security prompts the first time you use it. Neither one means
anything is wrong — this guide walks through exactly what you'll see and what to click.

## 1. "OmniFlow can't be opened because it is from an unidentified developer"

This appears the very first time you try to open the app after installing it.

**What to do:**

1. **Don't** double-click the app icon in `Applications` — that triggers the block again.
2. Instead, **right-click** (or Control-click) **OmniFlow** in `Applications` and choose **Open**
   from the menu.
3. A dialog appears asking "Are you sure you want to open it?" — click **Open**.

That's it. macOS remembers this choice, so you'll never see this warning again for this specific
version of the app.

**Alternative method**, if right-click → Open doesn't show an Open button:

1. Try double-clicking the app once (it will still be blocked).
2. Open **System Settings → Privacy & Security**.
3. Scroll down — you'll see a message like *"OmniFlow was blocked to protect your Mac"* with an
   **Open Anyway** button. Click it, then confirm in the dialog that follows.

> **Why does this happen?** macOS's Gatekeeper only trusts apps that are notarized by Apple or
> signed with a paid Developer ID. OmniFlow is signed "ad-hoc" (a free, local-only signature) so
> it can be freely distributed without a developer account — but that also means Gatekeeper
> doesn't recognize it as a "known" app on first launch. This is a standard step for any small,
> independently distributed macOS app, not a red flag.

## 2. "OmniFlow wants to use your confidential information stored in 'Chrome Safe Storage' in your keychain"

This one is **not required** to use OmniFlow — it only appears when you check or download a link
from **Instagram** or **Threads**, and only if you're logged into one of those in a browser on
this Mac (Chrome, Brave, Edge, Vivaldi, Opera, or Safari).

**What it's asking:** to download private or login-gated Instagram/Threads content (a Reel from
an account you follow, a Story, a private post), OmniFlow needs to reuse your *own* logged-in
browser session — the same way your browser already trusts you. To do that, it needs to read one
encrypted value macOS stores for your browser ("Chrome Safe Storage" is the name Chrome/Brave/Edge
all use for this, even though the exact dialog wording varies slightly by browser).

**What to click:** **Always Allow** is recommended — this lets Instagram/Threads downloads work
without asking again. If you click **Allow** (single-use) or **Deny**:

- **Allow (once):** works for that one download, but you may see the prompt again next time.
- **Deny:** OmniFlow simply won't be able to read that browser's session — Instagram/Threads
  downloads that need a login will fail with a "no session found" message, but every other
  platform (YouTube, TikTok, Facebook, RedNote, LinkedIn, X) is completely unaffected.

**Everything stays on your Mac.** This permission only lets OmniFlow read the session token
locally, on your own machine, to make a request to Instagram/Threads on your behalf — nothing is
ever sent anywhere else. See [Privacy](../README.md#privacy) in the main README.

> **Why might this prompt reappear after updating the app?** Each new version of OmniFlow you
> download is signed independently (see the Gatekeeper explanation above), and macOS Keychain
> ties this specific permission to the *exact* app version that asked for it. That means updating
> to a newer OmniFlow release can trigger this prompt again even if you already clicked "Always
> Allow" for a previous version — this is expected macOS behavior, not a bug, and clicking
> **Always Allow** again resolves it the same way.

## Still stuck?

If OmniFlow opens but check/download itself isn't working, that's a different issue — see
[Troubleshooting Check/Download Failures](TROUBLESHOOTING.md) instead.
