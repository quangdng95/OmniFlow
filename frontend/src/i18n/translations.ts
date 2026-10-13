export type Language = "en" | "vi";

export interface Translations {
  header: {
    menu: string;
    nav: { home: string; history: string; settings: string; terms: string; shortcut: string; changelog: string };
    home: { taglineLines: [string, string]; sub: string };
    settings: { title: string };
    terms: { title: string };
    shortcut: { title: string };
    changelog: { title: string };
    history: { title: string };
  };
  history: {
    heading: string;
    intro: string;
    empty: string;
    downloadAgain: string;
    copyLink: string;
    linkCopied: string;
    copyFailed: string;
    remove: string;
    clearAll: string;
    untitled: string;
  };
  footer: { by: string };
  login: { tagline: string; platforms: string; title: string; subtitle: string; label: string; placeholder: string; submit: string; submitting: string; wrong: string; locked: string; network: string; show: string; hide: string };
  urlInput: {
    fieldLabel: string;
    checkFailedTitle: string;
    placeholder: string;
    paste: string;
    pasting: string;
    checking: string;
    clearUrl: string;
    removeUrl: string;
  };
  checkingStatus: { checkingLink: string; cancel: string; keychainHint: string };
  playlist: {
    heading: string;
    empty: string;
    back: string;
    photo: string;
    video: string;
    selectAll: string;
    downloadSelected: string; // "Download {n} selected"
    truncated: string; // "Showing the first {n} videos only."
    itemProgress: string; // "Downloading item {i} of {n}…"
    batchDone: string; // "Saved {saved} of {total} videos"
    batchProgress: string; // "Downloading… ({done}/{n} done)"
    queued: string; // per-item: waiting
    failed: string; // per-item: errored
    showUnavailable: string; // filter toggle label
    unavailable: string; // per-item: hidden/removed video badge
    downloading: string; // per-row status
    downloaded: string; // per-row status (success)
    retry: string; // per-row action after a failure
    downloadAgain: string; // per-row action after success
    cancel: string; // stop the running batch
    totalItems: string; // "Total Items:"
    previewItem: string; // aria-label on a row thumbnail: "Preview {title}"
    previewHint: string; // screen-reader description of the preview dialog
    previousItem: string; // preview dialog: previous item
    nextItem: string; // preview dialog: next item
    downloadAll: string; // header bulk button
    orSelect: string; // "Or you can select items to download"
    download: string; // per-row idle action button
    downloadItemsSelected: string; // bulk button for a manual selection
    percentDownloading: string; // per-row: "{p}% Downloading"
    downloadedProgress: string; // global: "{done}/{total} Downloaded"
    savedItems: string; // global: "Saved: {n} Items"
    failedItems: string; // global: "Failed: {n} Items"
  };
  qualityAction: {
    selectQuality: string;
    startDownload: string;
    downloading: string;
    finalizing: string; // shown once the transfer hits 100% but the job is still merging/converting
    elapsedLabel: string; // accessible name of the counter next to the processing line
    slowHint: string; // under the quality picker when a 1440p+ option is selected
    keepCodec: string; // checkbox label: skip the H.264 conversion (fastest)
    keepCodecNote: string; // one line under it: the file may not open in QuickTime / on an iPhone
    webSlowWarning: string; // web only, 1440p+ without keep-codec: warns before the download starts
    converting: string; // processing line while the video is converted; {percent} is 0-100
    downloadAgain: string;
  };
  downloadProgress: { cancelDownload: string };
  downloadSuccess: { saved: string; openFolder: string; save: string; tryAgain: string; tapAgain: string; savedToDevice: string; downloadStarted: string; ready: string; batchSaved: string; batchReady: string; failedSuffix: string };
  home: {
    supportedPlatformsHeading: string;
    howToHeading: string;
    steps: string[];
    whyHeading: string;
    whyBody: string;
    faqHeading: string;
    faqs: { q: string; a: string }[];
  };
  downloadStatus: {
    cancelled: string;
    failedFallback: string;
  };
  settingsPage: {
    targetPath: {
      heading: string;
      description: string;
      browse: string;
      rememberPath: string;
    };
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
    language: {
      heading: string;
      description: string;
      english: string;
      vietnamese: string;
    };
    playlistLimit: {
      heading: string;
      description: string;
      option30: string;
      option50: string;
      option100: string;
      option200: string;
      option500: string;
      optionAll: string;
    };
    youtubeSignIn: {
      heading: string;
      description: string;
      keychainHint: string;
      off: string;
      noProfiles: string;
    };
    exportLogs: {
      heading: string;
      description: string;
      button: string;
      noLogsYet: string;
      opened: string;
    };
    resetSettings: {
      heading: string;
      description: string;
      button: string;
      confirm: string;
      done: string;
    };
  };
  terms: {
    heading: string;
    lastUpdatedLabel: string;
    lastUpdatedValue: string;
    intro: string;
    sections: { heading: string; body: string; list?: string[]; trailing?: string }[];
  };
  shortcutSetup: {
    eyebrow: string;
    heading: string;
    intro: string;
    warningTitle: string;
    warningBody: string;
    valuesTitle: string;
    valuesUrlLabel: string;
    copied: string;
    valuesTokenNote: string;
    phases: {
      num: string;
      title: string;
      desc: string;
      steps: { text: string; nested?: boolean }[];
    }[];
    footerNote: string;
  };
  languageSwitcher: { label: string; english: string; vietnamese: string };
  toast: { close: string }; // accessible name of every toast's X button
  apiErrors: {
    unreachable: string;
    requestFailed: string;
    requestFailedStatus: string; // "{status}" placeholder
    uploadFailed: string;
    fileFetchFailed: string; // "{status}" placeholder
  };
  changelog: {
    releases: { date: string; title: string; items: string[] }[];
  };
}

const en: Translations = {
  header: {
    menu: "Menu",
    nav: { home: "Home", history: "History", settings: "Settings", terms: "Terms of Use", shortcut: "Shortcut Setup", changelog: "Changelog" },
    home: {
      taglineLines: ["Paste a link.", "Get the file."],
      sub: "Free, no sign-up. Up to 4K, or audio only.",
    },
    settings: { title: "Settings" },
    terms: { title: "Terms of Use" },
    shortcut: { title: "iOS Shortcut Setup" },
    changelog: { title: "Changelog" },
    history: { title: "History" },
  },
  history: {
    heading: "Recent downloads",
    intro: "The last 10 links you downloaded on this device. They are stored only in this browser - nothing is sent to the server.",
    empty: "Nothing here yet. Links you download will show up here.",
    downloadAgain: "Download again",
    copyLink: "Copy link",
    linkCopied: "Link copied",
    copyFailed: "Couldn't copy the link",
    remove: "Remove from history",
    clearAll: "Clear history",
    untitled: "Untitled",
  },
  login: { tagline: "Save videos, music and photos in one tap.", platforms: "YouTube · TikTok · Instagram · Facebook · X · Threads · LinkedIn · RedNote", title: "Welcome to ViDrop", subtitle: "Enter your access token to continue.", label: "Access token", placeholder: "Paste your token", submit: "Unlock", submitting: "Unlocking…", wrong: "Incorrect token. Please try again.", locked: "Too many attempts. Try again in a few minutes.", network: "Could not reach the server. Check your connection.", show: "Show token", hide: "Hide token" },
  footer: { by: "By" },
  urlInput: {
    fieldLabel: "Video link",
    checkFailedTitle: "Couldn't check this link",
    placeholder: "Copy and Paste your url",
    paste: "Paste",
    pasting: "Pasting…",
    checking: "Checking",
    clearUrl: "Clear URL",
    removeUrl: "Remove URL",
  },
  checkingStatus: {
    checkingLink: "Checking Link…",
    cancel: "Cancel",
    keychainHint:
      "🔐 macOS may ask for Keychain permission to read your Instagram/Threads login from your browser — this is expected, click \"Always Allow\" so it only happens once.",
  },
  playlist: {
    heading: "Select items to download",
    empty: "This story has no downloadable video content.",
    back: "Back to list",
    photo: "Photo",
    video: "Video",
    selectAll: "Select all",
    downloadSelected: "Download {n} selected",
    truncated: "Large playlist/channel — showing the first {n} videos only.",
    itemProgress: "Downloading item {i} of {n}…",
    batchDone: "Saved {saved} of {total} videos",
    batchProgress: "Downloading… ({done}/{n} done)",
    queued: "Queued",
    failed: "Failed",
    showUnavailable: "Show unavailable videos",
    unavailable: "Unavailable",
    downloading: "Downloading…",
    downloaded: "Downloaded",
    retry: "Retry",
    downloadAgain: "Download again",
    cancel: "Cancel",
    totalItems: "Total Items:",
    previewItem: "Preview {title}",
    previewHint: "Enlarged thumbnail. Use the arrow keys to move between items.",
    previousItem: "Previous item",
    nextItem: "Next item",
    downloadAll: "Download All",
    orSelect: "Or you can select items to download",
    download: "Download",
    downloadItemsSelected: "Download Items Selected",
    percentDownloading: "{p}% Downloading",
    downloadedProgress: "{done}/{total} Downloaded",
    savedItems: "Saved: {n} Items",
    failedItems: "Failed: {n} Items",
  },
  qualityAction: {
    selectQuality: "Select Quality:",
    startDownload: "Start Download",
    downloading: "Downloading",
    finalizing: "Processing video…",
    elapsedLabel: "Time elapsed",
    slowHint: "High resolutions can take longer to process after the download.",
    keepCodec: "Keep original codec (fastest)",
    keepCodecNote: "Skips the conversion and saves a .mkv. It may not open in QuickTime or on an iPhone.",
    webSlowWarning: "4K needs converting and can take a few minutes. Choose “Keep original codec” to download right away (a .mkv file).",
    converting: "Converting to H.264… {percent}%",
    downloadAgain: "Download Again",
  },
  downloadProgress: { cancelDownload: "Cancel Download" },
  downloadSuccess: { saved: "Saved:", openFolder: "Open Folder", save: "Save to device", tryAgain: "Try download again", tapAgain: "Your files are ready - tap Save to device again.", savedToDevice: "Saved to your device", downloadStarted: "Download started - check your browser's download bar", ready: "Ready to save", batchSaved: "{saved} saved", batchReady: "{saved} ready to save", failedSuffix: ", {failed} failed" },
  home: {
    supportedPlatformsHeading: "Supported platforms",
    howToHeading: "How it works",
    steps: [
      "Copy the link of a video, photo or playlist.",
      "Paste it above, then pick video or audio and a quality.",
      "Select Start Download, then Save to device when it finishes.",
    ],
    whyHeading: "Why ViDrop",
    whyBody: "Free, no account. Single videos up to 4K, and whole playlists in one go.",
    faqHeading: "Questions",
    faqs: [
      {
        q: "Where are my files saved?",
        a: "In your Downloads folder on the desktop app. On a phone, tap Save to device when the download finishes.",
      },
      { q: "Is it really free?", a: "Yes. No account and no fees." },
      {
        q: "Can I download a whole playlist?",
        a: "Yes. Paste a YouTube playlist or channel link, then pick the videos.",
      },
      {
        q: "Why did my link fail?",
        a: "Private or deleted posts can't be downloaded. Check that the post is public, then try again.",
      },
    ],
  },
  downloadStatus: {
    cancelled: "Download cancelled",
    failedFallback: "Download failed",
  },
  settingsPage: {
    targetPath: {
      heading: "Target Path",
      description: "Here you can configure where the downloaded videos are to be saved.",
      browse: "Browse…",
      rememberPath: "Always save at the last used path.",
    },
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
    language: {
      heading: "Language",
      description: "Choose the language ViDrop uses. The change applies right away.",
      english: "English",
      vietnamese: "Vietnamese",
    },
    playlistLimit: {
      heading: "Playlist / Channel Loading Limit",
      description: "Choose the most videos to list from a YouTube playlist or channel. Lower values load faster. A YouTube Mix always lists 50, and an Instagram profile at most 30.",
      option30: "30 items (Fastest)",
      option50: "50 items",
      option100: "100 items (Recommended)",
      option200: "200 items",
      option500: "500 items",
      optionAll: "All items (Slowest, could hit rate limits)",
    },
    youtubeSignIn: {
      heading: "YouTube sign-in",
      description: "YouTube sometimes asks for a sign-in before it lets you download. Choose the Chrome profile where you're signed in to YouTube. ViDrop uses that YouTube login only when YouTube asks for it. Off by default.",
      keychainHint: "macOS may ask for Keychain access. Choose Always Allow, so it asks only once.",
      off: "Off",
      noProfiles: "No Chrome profile found on this Mac.",
    },
    exportLogs: {
      heading: "Diagnostic Logs",
      description: "If check/download keeps failing with a generic error, open the log folder below and send us the errors.log file — it records the real cause even when the app only shows a friendly message.",
      button: "Open Log Folder",
      noLogsYet: "No errors have been logged on this machine yet.",
      opened: "Log folder opened.",
    },
    resetSettings: {
      heading: "Reset App Data",
      description: "If check/download keeps failing for no clear reason, clearing ViDrop's saved settings (download path, saved cookies, etc.) and starting fresh can help — this does not delete any of your downloaded files.",
      button: "Clear Cache & Reset Settings",
      confirm: "This will reset your save folder, language, and saved settings back to default. Continue?",
      done: "Settings have been reset.",
    },
  },
  terms: {
    heading: "Terms of Use for ViDrop",
    lastUpdatedLabel: "Last Updated:",
    lastUpdatedValue: "27-02-2026",
    intro:
      "By accessing or using ViDrop, you agree to be bound by these Terms of Use. If you do not agree with any part of these terms, please stop using our service immediately.",
    sections: [
      {
        heading: "1. Our Service",
        body: "ViDrop is a free, general-purpose utility tool designed to help users download video and audio content from third-party platforms, including YouTube (with full support for playlists and channels), TikTok, Instagram, Facebook, RedNote, Threads, X (Twitter), and LinkedIn.",
      },
      {
        heading: "2. Personal & Non-Commercial Use",
        body: "We grant you a limited, non-exclusive right to use ViDrop strictly for your personal, non-commercial purposes. You agree not to use our service to license, sell, distribute, or commercially exploit any downloaded content.",
      },
      {
        heading: "3. Copyright & User Responsibility",
        body: "ViDrop acts only as a technical conduit. We do not host, store, or own any of the media content downloaded through our service.",
        list: [
          "Your Responsibility: You are solely responsible for the media you download. You must ensure you have the legal right, explicit permission, or fair-use justification from the rightful copyright owner to download and use the content.",
          "No Infringement: ViDrop does not encourage, condone, or support the unauthorized downloading or distribution of copyrighted material.",
        ],
      },
      {
        heading: "4. Acceptable Conduct",
        body: "To keep ViDrop running smoothly for everyone, you agree NOT to:",
        list: [
          "Use any automated scripts, bots, crawlers, or data mining tools on our website.",
          "Take any action that imposes an unreasonable load on our server infrastructure.",
          "Interfere with the security features of the website.",
          "Use the service for any illegal or unlawful purpose.",
        ],
        trailing:
          "We reserve the right to block IP addresses or terminate access for anyone violating these rules, without prior notice.",
      },
      {
        heading: "5. Disclaimer of Warranties",
        body: 'ViDrop is provided on an "AS-IS" and "AS-AVAILABLE" basis. While we strive for the best experience, we do not guarantee that the service will be entirely error-free, perfectly secure, or uninterrupted, especially since third-party platforms constantly update their systems.',
      },
      {
        heading: "6. Limitation of Liability",
        body: "To the maximum extent permitted by law, ViDrop and its team shall not be held liable for any direct, indirect, incidental, or consequential damages resulting from your use of the website, including but not limited to data loss, device issues, or legal claims from third parties regarding the content you download.",
      },
      {
        heading: "7. Changes to These Terms",
        body: "We reserve the right to modify these Terms at any time. Your continued use of ViDrop after any changes indicates your acceptance of the updated terms.",
      },
    ],
  },
  shortcutSetup: {
    eyebrow: "iOS Shortcut · build it once",
    heading: "Share a link → ViDrop downloads it",
    intro:
      "Watching something on Instagram/TikTok, hit Share → pick this shortcut → it calls this server and saves the file for you. Build it once, then share the shortcut itself so any other iPhone can use it too.",
    warningTitle: "⚠️ Not verified on a real iPhone yet",
    warningBody:
      "This is built exactly against the real API below (already verified end-to-end on the server side), but there's no way to remote into an iPhone and build/run it inside the Shortcuts app directly. Follow the phases in order, test with one short TikTok link first. If an action's name doesn't match what you see, or something errors, that's worth reporting so it can be fixed.",
    valuesTitle: "2 values used throughout",
    valuesUrlLabel: "Server base URL:",
    copied: "Copied",
    valuesTokenNote:
      "Token — get it by SSH-ing into the server (python3 -m remote_web.config show) or from whoever manages it. Never paste the real token into the shortcut and then share that shortcut publicly — anyone holding it can use this server the same way you can.",
    phases: [
      {
        num: "PHASE 0",
        title: "Create the shortcut",
        desc: 'Shortcuts app → tap + → name it "ViDrop Download"',
        steps: [
          {
            text: 'Tap the ⓘ (Shortcut Details) icon at the top → enable "Use as Share Sheet Action" → under Share Sheet Types, choose only URLs.',
          },
          {
            text: "Still works run manually (without the Share Sheet): copy the link first, then open the shortcut from the Home Screen — Phase 1 falls back to the clipboard when nothing was shared in.",
          },
        ],
      },
      {
        num: "PHASE 1",
        title: "Get the link",
        desc: "Prefer whatever was shared in; fall back to the clipboard",
        steps: [
          { text: "If Shortcut Input → Has No Value" },
          { text: "Get Clipboard", nested: true },
          { text: "Set Variable named Link = the Clipboard result", nested: true },
          { text: "Otherwise" },
          { text: "Set Variable named Link = Shortcut Input", nested: true },
          { text: "End If" },
        ],
      },
      {
        num: "PHASE 2",
        title: "Check the link",
        desc: "Calls /api/check — fails fast on a bad link or a playlist",
        steps: [
          { text: "Dictionary — add 1 key: url = variable Link" },
          {
            text: "Get Contents of URL — URL: {origin}/api/check · Method: POST · Headers: Authorization = Bearer TOKEN, Content-Type = application/json · Request Body: JSON → pick the Dictionary from the step above · → Set Variable CheckResult",
          },
          { text: "Get Dictionary Value — key error from CheckResult → Set Variable CheckError" },
          { text: "If CheckError → Has Any Value" },
          { text: "Show Alert — message = variable CheckError", nested: true },
          { text: "Stop This Shortcut", nested: true },
          { text: "End If" },
          { text: "Get Dictionary Value — key type from CheckResult → Set Variable LinkType" },
          { text: "If LinkType → is → playlist" },
          { text: "Open URLs — {origin}", nested: true },
          {
            text: 'Show Alert — "This link has multiple videos/photos — open the web app to pick one"',
            nested: true,
          },
          { text: "Stop This Shortcut", nested: true },
          { text: "End If" },
        ],
      },
      {
        num: "PHASE 3",
        title: "Start the download",
        desc: "Calls /api/download, grabs a job_id",
        steps: [
          { text: "Dictionary — 2 keys: url = variable Link · quality = text Best" },
          {
            text: "Get Contents of URL — URL: {origin}/api/download · Method: POST, same headers as Phase 2 · Request Body: JSON → the Dictionary you just made · → Set Variable DownloadResult",
          },
          { text: "Get Dictionary Value — key job_id from DownloadResult → Set Variable JobID" },
        ],
      },
      {
        num: "PHASE 4",
        title: "Wait for it to finish",
        desc: "Polls progress every 1.5s, up to 20 times (~30s)",
        steps: [
          { text: "Set Variable Done = false" },
          { text: "Repeat 20 times" },
          { text: "If Done → is → false", nested: true },
          { text: "Wait 1.5 seconds", nested: true },
          {
            text: "Get Contents of URL — URL: {origin}/api/progress/ + insert the JobID variable at the end · Method: GET, header Authorization = Bearer TOKEN · → Set Variable ProgressResult",
            nested: true,
          },
          { text: "Get Dictionary Value — key status from ProgressResult → Set Variable JobStatus", nested: true },
          { text: "If JobStatus → is → done", nested: true },
          { text: "Set Variable Done = true", nested: true },
          { text: "End If", nested: true },
          { text: "End If", nested: true },
          { text: "End Repeat" },
        ],
      },
      {
        num: "PHASE 5",
        title: "Save / open the file",
        desc: "Pulls down the real file, previews it so you can save it",
        steps: [
          { text: "If Done → is → true" },
          {
            text: "Get Contents of URL — URL: {origin}/api/download-file/ + insert JobID · Method: GET, header Authorization = Bearer TOKEN · The result is the real video/photo file",
            nested: true,
          },
          {
            text: "Quick Look the result above — tap the share button inside Quick Look to Save to Photos / Files / AirDrop",
            nested: true,
          },
          { text: "Otherwise" },
          { text: 'Show Alert — "Taking a while — open the web app to keep watching it"', nested: true },
          { text: "Open URLs — {origin}", nested: true },
          { text: "End If" },
        ],
      },
      {
        num: "PHASE 6",
        title: "Share it to another device",
        desc: "Same shortcut, same server/session as yours",
        steps: [
          { text: "Open the shortcut you just built → tap Share (top corner) → Copy iCloud Link" },
          {
            text: "Send that link over iMessage/whatever you like — anyone who taps it gets the exact same shortcut, ready to use",
          },
        ],
      },
    ],
    footerNote:
      "Server: remote_web, authenticated via the Authorization: Bearer header (added specifically for a headless client like this — the browser's own cookie login still works the same, side by side). The job's temp file on the server is deleted automatically once Phase 5 pulls it down.",
  },
  languageSwitcher: { label: "Language", english: "English", vietnamese: "Tiếng Việt" },
  toast: { close: "Close notification" },
  apiErrors: {
    unreachable: "Can't reach the ViDrop server. Make sure it's running, then reload this page.",
    requestFailed: "Request failed.",
    requestFailedStatus: "Request failed ({status}).",
    uploadFailed: "Upload failed.",
    fileFetchFailed: "Failed to fetch file ({status})",
  },
  changelog: {
    releases: [
      {
        date: "2026-10-13",
        title: "ViDrop 2.0: a new Mac app, eight platforms checked",
        items: [
          "A new ViDrop Mac app, with its own name and icon. The first time you open it, your settings are copied over from the old app. The old app's data stays untouched.",
          "History and your language choice are now kept after you close the Mac app.",
          "YouTube sign-in is now in Settings. Pick your Chrome profile so YouTube downloads work when YouTube asks you to sign in. It is off by default.",
          "Pasting a YouTube channel link now lists its videos.",
          "A failed or cancelled download no longer leaves partial files in your folder, and never touches other files with a similar name.",
          "Clearer messages for an expired RedNote link, and for \"Audio Only\" on a video with no sound.",
          "We checked all eight platforms with real links: YouTube, TikTok, Instagram, Facebook, X, Threads, LinkedIn and RedNote. The README now says what works on each.",
        ],
      },
      {
        date: "2026-10-13",
        title: "Meet ViDrop: a new look, clearer messages",
        items: [
          "The app is now called ViDrop, with a new square yellow logo.",
          "A new design on every page: bold type in black and yellow.",
          "Playlist pages are more compact. The title is shorter, and Total Items sits next to Download All, so you can start without scrolling.",
          "A timer now runs next to \"Processing video…\", and a note tells you when 1440p or 4K will take longer.",
          "When a download finishes you get a message on the page, plus a system notification if the tab is in the background.",
          "Error messages are clearer. You no longer see raw technical errors or GitHub links when a link can't be read.",
          "Threads share links (threads.com/share/…) now work.",
          "Short links from LinkedIn (lnkd.in), X (t.co) and Facebook (fb.me) open automatically.",
          "LinkedIn slide-deck posts save every page as an image, not just the cover.",
          "RedNote links work again.",
          "Fixed page sections that didn't line up, and a close button on notifications that was hard to tap on a phone.",
          "The \"showing the first videos only\" notice now follows your Settings. It no longer appears for a list that fits your loading limit.",
          "Settings and help text now match what the app does. For example, a language change applies right away, with no restart.",
        ],
      },
      {
        date: "2026-09-30",
        title: "History tab, TikTok audio, and saving fixes",
        items: [
          "New History tab: the last 10 links you downloaded on this device. Download again, copy a link, or remove entries. It is stored only in your browser - nothing is sent to the server.",
          "TikTok videos can now be saved as audio only (MP3) even when the video is fetched through the backup service - before, only the video was offered.",
          "Fixed some TikTok videos playing with picture but no sound on iPhone/Mac: their audio came as MP3 inside the video, which Apple players cannot play. It is now converted to AAC automatically (the picture is untouched).",
          "Fixed \"The request is not allowed…\" when saving a large batch to an iPhone: the files are now prepared before you tap the save button.",
          "Already-downloaded rows can be ticked again, and both the checkbox and the whole row now select it. The save button is renamed \"Save to device\" and also appears next to Download All.",
          "After you save to your device you now get a confirmation message. All action buttons are now the same size, and each download row fits properly on a phone.",
        ],
      },
      {
        date: "2026-09-25",
        title: "Easy English ⇄ Tiếng Việt switch",
        items: [
          "New EN | VI switch at the top of every page — no more digging through Settings. On a device set to Vietnamese, the app now starts in Vietnamese by itself.",
          "Error messages from the server (couldn't read a link, private account, missing FFmpeg…) now follow the language you picked instead of always being Vietnamese.",
          "The cloud sign-in page is translated too, with its own English / Tiếng Việt link.",
          "Fixed the top menu being cut off on phones — the items now wrap onto a second line so none are out of reach.",
          "Translated the last leftover English texts (\"Supported Platforms\", connection errors).",
        ],
      },
      {
        date: "2026-09-25",
        title: "Facebook downloads no longer hang on the cloud server",
        items: [
          "Fixed Facebook downloads on the cloud server getting stuck at \"100%\" for minutes and slowing every other request down. Some Facebook videos only offer their top quality in AV1, which the server was re-encoding to H.264 on a tiny CPU — it now takes Facebook's ready-made H.264 version instead.",
          "Trade-off: on the cloud server, a Facebook video whose 1080p version exists only in AV1 now downloads at 720p H.264. The desktop app is unchanged.",
          "When a download reaches 100% but is still being processed, the progress now says \"Processing video…\" instead of looking frozen.",
        ],
      },
      {
        date: "2026-09-18",
        title: "TikTok & download reliability fixes",
        items: [
          "Fixed TikTok Photo Mode/carousel thumbnails not showing correctly for some posts.",
          "Fixed the \"Retry\" button on a failed download sometimes failing with a 404 error instead of retrying.",
          "Fixed bulk-saving multiple photos/videos to your iPhone's Photos app so every item saves, not just the first one.",
        ],
      },
      {
        date: "2026-09-16",
        title: "YouTube fix, API tokens, mobile Share Sheet saves",
        items: [
          "Fixed YouTube downloads breaking after YouTube rolled out a newer anti-bot streaming protocol (SABR).",
          "Added secure API token (Bearer) authentication, so ViDrop can be automated from other apps/devices — like the new iOS Shortcut below — without logging in through a browser each time.",
          "Sharing a link straight from Instagram/TikTok/etc. to ViDrop on your phone (via the Share Sheet) now saves the result directly, including bulk saves.",
          "New: an iOS Shortcut Setup guide — build a Share-Sheet shortcut once so any iPhone can send a link to your ViDrop server and get the file back, no browser needed.",
          "Locked remote SSH/server management down to the app's own purchase gate, closing an access path that shouldn't have been open.",
        ],
      },
      {
        date: "2026-08-29 → 2026-09-10",
        title: "Remote access: use ViDrop from your phone",
        items: [
          "Added Remote Web Access — run ViDrop on your own small cloud server and reach it securely from your phone or any device via a private URL, protected by a login/trust-cookie gate.",
          "Batch downloads (playlists, carousels) over remote access now assemble into a single ZIP you download in one go.",
          "Instagram/Threads login sessions now sync from your Mac to a cloud server, so authenticated downloads keep working even when ViDrop isn't running on your own machine.",
          "Added a manual cookies.txt upload option for headless/cloud servers that have no browser to auto-extract cookies from.",
          "Fixed ffmpeg not being found on Linux-based cloud servers.",
        ],
      },
      {
        date: "2026-08-29 → 2026-08-30",
        title: "TikTok Photo Mode + smarter fallbacks",
        items: [
          "Added support for downloading TikTok \"Photo Mode\" posts (multi-image slideshows) — previously unsupported entirely.",
          "Fixed TikTok video downloads breaking after an upstream TikTok change — downloads now automatically fall back to a working method when the primary one fails.",
          "Fixed a LinkedIn video download bug.",
          "Rebuilt the bundled ffmpeg as a native Apple Silicon build for a real speed boost on M-series Macs (it was previously running under Rosetta 2 emulation).",
          "Hardened error handling so a failed check/download never surfaces a raw, confusing technical error.",
        ],
      },
      {
        date: "2026-07-10",
        title: "Instagram/Threads fixes, self-serve diagnostics",
        items: [
          "Fixed the root cause of check/download failing entirely on a freshly-installed Mac (a broken bundled SSL certificate path).",
          "Fixed a Chrome cookie-reading bug that could silently miss a just-logged-in Instagram/Threads session.",
          "Fixed a misleading \"Private account\" message that could appear when the real cause was an expired session.",
          "Added Diagnostic Logs and Reset App Data to Settings, so a failure can be self-diagnosed and reported.",
          "Pasting a platform's full \"Share\" text (title, hashtags and all) now works, not just a bare URL.",
          "UI polish pass to match the Figma design pixel-for-pixel (logo colors, spacing, contrast).",
        ],
      },
    ],
  },
};

const vi: Translations = {
  header: {
    menu: "Menu",
    nav: { home: "Trang chủ", history: "Lịch sử", settings: "Cài đặt", terms: "Điều khoản sử dụng", shortcut: "Cài Shortcut", changelog: "Nhật ký cập nhật" },
    home: {
      taglineLines: ["Dán link.", "Nhận file."],
      sub: "Miễn phí, không cần đăng ký. Tối đa 4K hoặc chỉ lấy âm thanh.",
    },
    settings: { title: "Cài đặt" },
    terms: { title: "Điều khoản sử dụng" },
    shortcut: { title: "Cài đặt iOS Shortcut" },
    changelog: { title: "Nhật ký cập nhật" },
    history: { title: "Lịch sử" },
  },
  history: {
    heading: "Tải xuống gần đây",
    intro: "10 liên kết bạn đã tải gần nhất trên thiết bị này. Chúng chỉ được lưu trong trình duyệt này - không gửi gì lên server.",
    empty: "Chưa có gì ở đây. Các liên kết bạn đã tải sẽ hiện ở đây.",
    downloadAgain: "Tải lại",
    copyLink: "Sao chép liên kết",
    linkCopied: "Đã sao chép liên kết",
    copyFailed: "Không sao chép được liên kết",
    remove: "Xoá khỏi lịch sử",
    clearAll: "Xoá lịch sử",
    untitled: "Chưa có tiêu đề",
  },
  login: { tagline: "Lưu video, nhạc và ảnh chỉ với một chạm.", platforms: "YouTube · TikTok · Instagram · Facebook · X · Threads · LinkedIn · RedNote", title: "Chào mừng đến ViDrop", subtitle: "Nhập mã truy cập để tiếp tục.", label: "Mã truy cập", placeholder: "Dán mã của bạn", submit: "Mở khoá", submitting: "Đang mở khoá…", wrong: "Mã không đúng. Vui lòng thử lại.", locked: "Thử quá nhiều lần. Vui lòng thử lại sau vài phút.", network: "Không kết nối được máy chủ. Kiểm tra mạng của bạn.", show: "Hiện mã", hide: "Ẩn mã" },
  footer: { by: "Bởi" },
  urlInput: {
    fieldLabel: "Link video",
    checkFailedTitle: "Không kiểm tra được link này",
    placeholder: "Sao chép và dán đường dẫn của bạn",
    paste: "Dán",
    pasting: "Đang dán…",
    checking: "Đang kiểm tra",
    clearUrl: "Xoá đường dẫn",
    removeUrl: "Gỡ đường dẫn",
  },
  checkingStatus: {
    checkingLink: "Đang kiểm tra đường dẫn…",
    cancel: "Huỷ",
    keychainHint:
      "🔐 macOS có thể hỏi quyền Keychain để đọc phiên đăng nhập Instagram/Threads từ trình duyệt của bạn — đây là điều bình thường, hãy chọn \"Always Allow\" để chỉ cần cấp quyền một lần.",
  },
  playlist: {
    heading: "Chọn các mục để tải",
    empty: "Story này không có video nào để tải.",
    back: "Quay lại danh sách",
    photo: "Ảnh",
    video: "Video",
    selectAll: "Chọn tất cả",
    downloadSelected: "Tải {n} mục đã chọn",
    truncated: "Playlist/kênh lớn — chỉ hiển thị {n} video đầu tiên.",
    itemProgress: "Đang tải mục {i}/{n}…",
    batchDone: "Đã tải {saved}/{total} video",
    batchProgress: "Đang tải… (xong {done}/{n})",
    queued: "Đang chờ",
    failed: "Lỗi",
    showUnavailable: "Hiện video không khả dụng",
    unavailable: "Không khả dụng",
    downloading: "Đang tải…",
    downloaded: "Đã tải",
    retry: "Thử lại",
    downloadAgain: "Tải lại",
    cancel: "Huỷ",
    totalItems: "Tổng số mục:",
    previewItem: "Xem trước {title}",
    previewHint: "Ảnh thu nhỏ được phóng to. Dùng phím mũi tên để chuyển giữa các mục.",
    previousItem: "Mục trước",
    nextItem: "Mục sau",
    downloadAll: "Tải tất cả",
    orSelect: "Hoặc bạn có thể chọn từng mục để tải",
    download: "Tải",
    downloadItemsSelected: "Tải các mục đã chọn",
    percentDownloading: "{p}% Đang tải",
    downloadedProgress: "Đã tải {done}/{total}",
    savedItems: "Đã lưu: {n} mục",
    failedItems: "Lỗi: {n} mục",
  },
  qualityAction: {
    selectQuality: "Chọn chất lượng:",
    startDownload: "Bắt đầu tải xuống",
    downloading: "Đang tải xuống",
    finalizing: "Đang xử lý video…",
    elapsedLabel: "Thời gian đã trôi qua",
    slowHint: "Độ phân giải cao có thể mất nhiều thời gian xử lý hơn sau khi tải.",
    keepCodec: "Giữ codec gốc (nhanh nhất)",
    keepCodecNote: "Bỏ qua bước chuyển đổi và lưu thành file .mkv. File có thể không mở được bằng QuickTime hoặc trên iPhone.",
    webSlowWarning: "4K cần chuyển mã và có thể mất vài phút. Chọn “Giữ codec gốc” để tải ngay (file .mkv).",
    converting: "Đang chuyển sang H.264… {percent}%",
    downloadAgain: "Tải lại",
  },
  downloadProgress: { cancelDownload: "Huỷ tải xuống" },
  downloadSuccess: { saved: "Đã lưu:", openFolder: "Mở thư mục", save: "Lưu về máy", tryAgain: "Thử tải lại", tapAgain: "Tệp đã sẵn sàng - bấm Lưu về máy lần nữa.", savedToDevice: "Đã lưu về máy của bạn", downloadStarted: "Đã bắt đầu tải - xem thanh tải xuống của trình duyệt", ready: "Sẵn sàng để lưu", batchSaved: "Đã lưu {saved} mục", batchReady: "{saved} mục sẵn sàng để lưu", failedSuffix: ", {failed} mục lỗi" },
  home: {
    supportedPlatformsHeading: "Nền tảng được hỗ trợ",
    howToHeading: "Cách dùng",
    steps: [
      "Sao chép link của video, ảnh hoặc danh sách phát.",
      "Dán vào ô phía trên, rồi chọn video hay âm thanh và chất lượng.",
      "Bấm Bắt đầu tải xuống, sau đó Lưu về máy khi tải xong.",
    ],
    whyHeading: "Vì sao chọn ViDrop",
    whyBody: "Miễn phí, không cần tài khoản. Video lẻ tối đa 4K, tải cả danh sách phát một lần.",
    faqHeading: "Câu hỏi thường gặp",
    faqs: [
      {
        q: "File được lưu ở đâu?",
        a: "Trong thư mục Tải xuống nếu dùng ứng dụng máy tính. Trên điện thoại, bấm Lưu về máy khi tải xong.",
      },
      { q: "Có thật sự miễn phí không?", a: "Có. Không cần tài khoản, không mất phí." },
      {
        q: "Có tải được cả danh sách phát không?",
        a: "Có. Dán link danh sách phát hoặc kênh YouTube, rồi chọn các video cần tải.",
      },
      {
        q: "Vì sao link của tôi lỗi?",
        a: "Bài riêng tư hoặc đã xoá thì không tải được. Hãy kiểm tra bài đăng ở chế độ công khai rồi thử lại.",
      },
    ],
  },
  downloadStatus: {
    cancelled: "Đã huỷ tải xuống",
    failedFallback: "Tải xuống thất bại",
  },
  settingsPage: {
    targetPath: {
      heading: "Thư mục lưu",
      description: "Tại đây bạn có thể cấu hình nơi lưu các video đã tải xuống.",
      browse: "Chọn thư mục…",
      rememberPath: "Luôn lưu vào thư mục đã dùng gần nhất.",
    },
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
    language: {
      heading: "Ngôn ngữ",
      description: "Chọn ngôn ngữ ViDrop sử dụng. Thay đổi có hiệu lực ngay.",
      english: "Tiếng Anh",
      vietnamese: "Tiếng Việt",
    },
    playlistLimit: {
      heading: "Giới hạn tải Playlist / Kênh",
      description: "Chọn số video tối đa để liệt kê từ một playlist hoặc kênh YouTube. Giá trị nhỏ tải nhanh hơn. YouTube Mix luôn liệt kê 50 video, và trang Instagram tối đa 30.",
      option30: "30 video (Nhanh nhất)",
      option50: "50 video",
      option100: "100 video (Khuyên dùng)",
      option200: "200 video",
      option500: "500 video",
      optionAll: "Tất cả video (Chậm nhất, có thể bị giới hạn chặn)",
    },
    youtubeSignIn: {
      heading: "Đăng nhập YouTube",
      description: "Đôi khi YouTube yêu cầu đăng nhập trước khi cho tải. Hãy chọn profile Chrome mà bạn đã đăng nhập YouTube. ViDrop chỉ dùng phiên YouTube đó khi YouTube yêu cầu. Mặc định đang tắt.",
      keychainHint: "macOS có thể hỏi quyền Keychain. Hãy chọn \"Luôn cho phép\" để chỉ hỏi một lần.",
      off: "Tắt",
      noProfiles: "Không tìm thấy profile Chrome nào trên máy Mac này.",
    },
    exportLogs: {
      heading: "Nhật ký chẩn đoán",
      description: "Nếu việc check/tải liên tục báo lỗi chung chung, hãy mở thư mục log bên dưới và gửi file errors.log cho chúng tôi — file này ghi lại nguyên nhân thật sự ngay cả khi app chỉ hiển thị một thông báo thân thiện.",
      button: "Mở thư mục Log",
      noLogsYet: "Chưa có lỗi nào được ghi lại trên máy này.",
      opened: "Đã mở thư mục log.",
    },
    resetSettings: {
      heading: "Đặt lại dữ liệu ứng dụng",
      description: "Nếu việc check/tải liên tục báo lỗi không rõ nguyên nhân, xóa cấu hình đã lưu của ViDrop (thư mục lưu, cookies đã lưu, v.v.) và bắt đầu lại từ đầu có thể giúp ích — thao tác này không xóa bất kỳ file đã tải nào của bạn.",
      button: "Xóa Cache & Đặt lại Cài đặt",
      confirm: "Thao tác này sẽ đặt lại thư mục lưu, ngôn ngữ và các cài đặt đã lưu về mặc định. Tiếp tục?",
      done: "Đã đặt lại cài đặt.",
    },
  },
  terms: {
    heading: "Điều khoản sử dụng ViDrop",
    lastUpdatedLabel: "Cập nhật lần cuối:",
    lastUpdatedValue: "27-02-2026",
    intro:
      "Khi truy cập hoặc sử dụng ViDrop, bạn đồng ý tuân theo các Điều khoản sử dụng này. Nếu bạn không đồng ý với bất kỳ phần nào trong các điều khoản này, vui lòng ngừng sử dụng dịch vụ của chúng tôi ngay lập tức.",
    sections: [
      {
        heading: "1. Dịch vụ của chúng tôi",
        body: "ViDrop là một công cụ tiện ích miễn phí, đa năng, được thiết kế để giúp người dùng tải video và âm thanh từ các nền tảng bên thứ ba, bao gồm YouTube (hỗ trợ đầy đủ danh sách phát và kênh), TikTok, Instagram, Facebook, RedNote, Threads, X (Twitter) và LinkedIn.",
      },
      {
        heading: "2. Sử dụng cá nhân & phi thương mại",
        body: "Chúng tôi cấp cho bạn quyền hạn chế, không độc quyền để sử dụng ViDrop chỉ cho mục đích cá nhân, phi thương mại. Bạn đồng ý không sử dụng dịch vụ của chúng tôi để cấp phép, bán, phân phối hoặc khai thác thương mại bất kỳ nội dung nào đã tải xuống.",
      },
      {
        heading: "3. Bản quyền & Trách nhiệm của người dùng",
        body: "ViDrop chỉ đóng vai trò là công cụ kỹ thuật trung gian. Chúng tôi không lưu trữ, sở hữu bất kỳ nội dung media nào được tải xuống thông qua dịch vụ của chúng tôi.",
        list: [
          "Trách nhiệm của bạn: Bạn hoàn toàn chịu trách nhiệm về nội dung mình tải xuống. Bạn phải đảm bảo có quyền hợp pháp, được cho phép rõ ràng, hoặc có căn cứ sử dụng hợp lý từ chủ sở hữu bản quyền hợp pháp để tải xuống và sử dụng nội dung đó.",
          "Không vi phạm: ViDrop không khuyến khích, dung túng hay hỗ trợ việc tải xuống hoặc phân phối trái phép nội dung có bản quyền.",
        ],
      },
      {
        heading: "4. Hành vi được chấp nhận",
        body: "Để ViDrop vận hành trơn tru cho mọi người, bạn đồng ý KHÔNG:",
        list: [
          "Sử dụng bất kỳ script tự động, bot, crawler hoặc công cụ khai thác dữ liệu nào trên website của chúng tôi.",
          "Thực hiện bất kỳ hành động nào gây tải trọng bất hợp lý lên hạ tầng máy chủ của chúng tôi.",
          "Can thiệp vào các tính năng bảo mật của website.",
          "Sử dụng dịch vụ cho bất kỳ mục đích bất hợp pháp hoặc trái luật nào.",
        ],
        trailing:
          "Chúng tôi có quyền chặn địa chỉ IP hoặc chấm dứt quyền truy cập đối với bất kỳ ai vi phạm các quy tắc này mà không cần báo trước.",
      },
      {
        heading: "5. Từ chối bảo đảm",
        body: 'ViDrop được cung cấp trên cơ sở "NGUYÊN TRẠNG" và "TUỲ THEO SẴN CÓ". Mặc dù chúng tôi luôn cố gắng mang lại trải nghiệm tốt nhất, chúng tôi không đảm bảo dịch vụ sẽ hoàn toàn không có lỗi, an toàn tuyệt đối hoặc không bị gián đoạn, đặc biệt khi các nền tảng bên thứ ba liên tục thay đổi hệ thống của họ.',
      },
      {
        heading: "6. Giới hạn trách nhiệm pháp lý",
        body: "Trong phạm vi tối đa được pháp luật cho phép, ViDrop và đội ngũ của chúng tôi sẽ không chịu trách nhiệm cho bất kỳ thiệt hại trực tiếp, gián tiếp, ngẫu nhiên hay hệ quả nào phát sinh từ việc bạn sử dụng website, bao gồm nhưng không giới hạn ở mất dữ liệu, hư hỏng thiết bị, hoặc khiếu nại pháp lý từ bên thứ ba liên quan đến nội dung bạn tải xuống.",
      },
      {
        heading: "7. Thay đổi điều khoản",
        body: "Chúng tôi có quyền chỉnh sửa các Điều khoản này bất kỳ lúc nào. Việc bạn tiếp tục sử dụng ViDrop sau khi có thay đổi đồng nghĩa với việc bạn chấp nhận các điều khoản đã cập nhật.",
      },
    ],
  },
  shortcutSetup: {
    eyebrow: "iOS Shortcut · tự build 1 lần",
    heading: "Share link → ViDrop tự tải",
    intro:
      "Coi video trên Instagram/TikTok, bấm Share → chọn shortcut này → nó tự gọi server này, tải xong tự lưu file. Build 1 lần, xong share iCloud link của chính cái shortcut đó cho máy khác xài chung.",
    warningTitle: "⚠️ Chưa test trên iPhone thật",
    warningBody:
      "Thiết kế đúng theo API thật bên dưới (đã test end-to-end phía server), nhưng không remote vào iPhone để tự tay build + chạy thử trong app Shortcuts được. Làm đúng thứ tự các Phase, test với 1 link TikTok ngắn trước. Bước nào tên action không khớp hoặc lỗi thì đáng để báo lại chỉnh.",
    valuesTitle: "2 giá trị dùng xuyên suốt",
    valuesUrlLabel: "Base URL của server:",
    copied: "Đã copy",
    valuesTokenNote:
      "Token — lấy bằng cách SSH vào server (python3 -m remote_web.config show) hoặc hỏi người quản trị. Đừng dán token thật vào shortcut rồi share công khai — ai cầm được file cũng xài chung được server này y như mày.",
    phases: [
      {
        num: "PHASE 0",
        title: "Tạo shortcut mới",
        desc: 'App Shortcuts → dấu + → đặt tên "ViDrop Tải Video"',
        steps: [
          {
            text: 'Bấm icon ⓘ (Shortcut Details) ở góc trên → bật "Use as Share Sheet Action" → mục Share Sheet Types chỉ chọn URLs.',
          },
          {
            text: "Vẫn chạy được kiểu thủ công (không qua Share Sheet): cứ copy link trước rồi mở shortcut từ Home Screen — Phase 1 tự đọc Clipboard nếu không có gì được share vào.",
          },
        ],
      },
      {
        num: "PHASE 1",
        title: "Lấy link",
        desc: "Ưu tiên link được share vào, không có thì lấy từ Clipboard",
        steps: [
          { text: "If Shortcut Input → Has No Value" },
          { text: "Get Clipboard", nested: true },
          { text: "Set Variable tên Link = kết quả Clipboard", nested: true },
          { text: "Otherwise" },
          { text: "Set Variable tên Link = Shortcut Input", nested: true },
          { text: "End If" },
        ],
      },
      {
        num: "PHASE 2",
        title: "Check link",
        desc: "Gọi /api/check — báo lỗi sớm nếu link hỏng hoặc là playlist",
        steps: [
          { text: "Dictionary — thêm 1 key: url = biến Link" },
          {
            text: "Get Contents of URL — URL: {origin}/api/check · Method: POST · Headers: Authorization = Bearer TOKEN, Content-Type = application/json · Request Body: JSON → chọn Dictionary ở bước trước · → Set Variable CheckResult",
          },
          { text: "Get Dictionary Value — key error từ CheckResult → Set Variable CheckError" },
          { text: "If CheckError → Has Any Value" },
          { text: "Show Alert — nội dung = biến CheckError", nested: true },
          { text: "Stop This Shortcut", nested: true },
          { text: "End If" },
          { text: "Get Dictionary Value — key type từ CheckResult → Set Variable LinkType" },
          { text: "If LinkType → is → playlist" },
          { text: "Open URLs — {origin}", nested: true },
          { text: 'Show Alert — "Link này nhiều video/ảnh — mở web để chọn item nhé"', nested: true },
          { text: "Stop This Shortcut", nested: true },
          { text: "End If" },
        ],
      },
      {
        num: "PHASE 3",
        title: "Bắt đầu tải",
        desc: "Gọi /api/download, lấy job_id",
        steps: [
          { text: "Dictionary — 2 key: url = biến Link · quality = chữ Best" },
          {
            text: "Get Contents of URL — URL: {origin}/api/download · Method: POST, headers giống Phase 2 · Request Body: JSON → Dictionary vừa tạo · → Set Variable DownloadResult",
          },
          { text: "Get Dictionary Value — key job_id từ DownloadResult → Set Variable JobID" },
        ],
      },
      {
        num: "PHASE 4",
        title: "Chờ tải xong",
        desc: "Hỏi tiến độ mỗi 1.5 giây, tối đa 20 lần (~30s)",
        steps: [
          { text: "Set Variable Done = false" },
          { text: "Repeat 20 lần" },
          { text: "If Done → is → false", nested: true },
          { text: "Wait 1.5 giây", nested: true },
          {
            text: "Get Contents of URL — URL: {origin}/api/progress/ + chèn biến JobID vào cuối · Method: GET, header Authorization = Bearer TOKEN · → Set Variable ProgressResult",
            nested: true,
          },
          { text: "Get Dictionary Value — key status từ ProgressResult → Set Variable JobStatus", nested: true },
          { text: "If JobStatus → is → done", nested: true },
          { text: "Set Variable Done = true", nested: true },
          { text: "End If", nested: true },
          { text: "End If", nested: true },
          { text: "End Repeat" },
        ],
      },
      {
        num: "PHASE 5",
        title: "Lưu / mở file",
        desc: "Tải file thật về, mở preview để lưu vào Ảnh hoặc Files",
        steps: [
          { text: "If Done → is → true" },
          {
            text: "Get Contents of URL — URL: {origin}/api/download-file/ + chèn biến JobID · Method: GET, header Authorization = Bearer TOKEN · Kết quả chính là file video/ảnh thật",
            nested: true,
          },
          {
            text: "Quick Look kết quả bước trên — bấm nút share ở Quick Look để Save to Photos / Files / AirDrop",
            nested: true,
          },
          { text: "Otherwise" },
          { text: 'Show Alert — "Tải hơi lâu, mở web coi tiếp nha"', nested: true },
          { text: "Open URLs — {origin}", nested: true },
          { text: "End If" },
        ],
      },
      {
        num: "PHASE 6",
        title: "Share qua máy khác",
        desc: "Cùng 1 shortcut, dùng chung server/session",
        steps: [
          { text: "Mở shortcut vừa build → bấm nút Share (góc trên) → Copy iCloud Link" },
          {
            text: "Gửi link đó qua iMessage/Zalo/gì cũng được → máy nào bấm vào cũng add được y chang, xài luôn",
          },
        ],
      },
    ],
    footerNote:
      "Server: remote_web, xác thực qua header Authorization: Bearer (thêm riêng cho client kiểu này — cookie trình duyệt vẫn hoạt động bình thường song song). Job tải xong tự xoá file tạm trên server sau khi Phase 5 lấy về máy.",
  },
  languageSwitcher: { label: "Ngôn ngữ", english: "English", vietnamese: "Tiếng Việt" },
  toast: { close: "Đóng thông báo" },
  apiErrors: {
    unreachable: "Không kết nối được tới máy chủ ViDrop. Hãy đảm bảo máy chủ đang chạy rồi tải lại trang.",
    requestFailed: "Yêu cầu thất bại.",
    requestFailedStatus: "Yêu cầu thất bại ({status}).",
    uploadFailed: "Tải lên thất bại.",
    fileFetchFailed: "Không lấy được tệp ({status}).",
  },
  changelog: {
    releases: [
      {
        date: "13-10-2026",
        title: "ViDrop 2.0: app Mac mới, tám nền tảng đã kiểm tra",
        items: [
          "App ViDrop mới cho Mac, có tên và biểu tượng riêng. Lần đầu mở, cài đặt của bạn được sao chép từ app cũ. Dữ liệu của app cũ vẫn được giữ nguyên.",
          "Lịch sử và ngôn ngữ bạn chọn giờ được giữ lại sau khi đóng app Mac.",
          "Đăng nhập YouTube giờ nằm trong Cài đặt. Hãy chọn profile Chrome để tải YouTube được khi YouTube yêu cầu đăng nhập. Mặc định đang tắt.",
          "Dán link kênh YouTube giờ sẽ liệt kê các video của kênh.",
          "Tải lỗi hoặc bị hủy không còn để lại file dở trong thư mục của bạn, và không động tới các file khác có tên gần giống.",
          "Thông báo rõ hơn khi link RedNote hết hạn, và khi chọn \"Audio Only\" cho video không có tiếng.",
          "Chúng tôi đã kiểm tra cả tám nền tảng bằng link thật: YouTube, TikTok, Instagram, Facebook, X, Threads, LinkedIn và RedNote. README giờ nêu rõ từng nền tảng dùng được những gì.",
        ],
      },
      {
        date: "13-10-2026",
        title: "Chào ViDrop: giao diện mới, thông báo rõ ràng hơn",
        items: [
          "Ứng dụng giờ có tên ViDrop, cùng logo vuông màu vàng mới.",
          "Giao diện mới trên mọi trang: chữ đậm, hai màu đen và vàng.",
          "Trang danh sách phát gọn hơn. Tiêu đề ngắn lại, Tổng số mục nằm cạnh nút Tải tất cả nên bạn bắt đầu tải mà không cần cuộn.",
          "Có đồng hồ đếm giây cạnh dòng \"Đang xử lý video…\", kèm lưu ý khi 1440p hoặc 4K cần nhiều thời gian hơn.",
          "Tải xong, bạn thấy thông báo ngay trên trang, và có thêm thông báo hệ thống nếu tab đang ở nền.",
          "Thông báo lỗi dễ hiểu hơn. Bạn không còn thấy lỗi kỹ thuật thô hay liên kết GitHub khi không đọc được một link.",
          "Link chia sẻ của Threads (threads.com/share/…) đã dùng được.",
          "Link rút gọn của LinkedIn (lnkd.in), X (t.co) và Facebook (fb.me) được mở tự động.",
          "Bài LinkedIn dạng slide lưu đủ từng trang thành ảnh, không chỉ trang bìa.",
          "Link RedNote đã dùng lại được.",
          "Sửa lỗi các phần của trang bị lệch hàng, và nút đóng thông báo khó bấm trên điện thoại.",
          "Thông báo \"chỉ hiện các video đầu tiên\" giờ theo đúng Cài đặt của bạn. Nó không còn hiện với danh sách nằm trong giới hạn bạn đã chọn.",
          "Chữ trong Cài đặt và phần trợ giúp giờ khớp với cách app hoạt động. Ví dụ, đổi ngôn ngữ có hiệu lực ngay, không cần khởi động lại.",
        ],
      },
      {
        date: "30-09-2026",
        title: "Tab Lịch sử, âm thanh TikTok và sửa lỗi lưu về máy",
        items: [
          "Thêm tab Lịch sử: 10 liên kết bạn đã tải gần nhất trên thiết bị này. Có thể tải lại, sao chép liên kết hoặc xoá từng mục. Dữ liệu chỉ lưu trong trình duyệt của bạn - không gửi gì lên server.",
          "Video TikTok giờ có thể lưu riêng âm thanh (MP3) kể cả khi video được lấy qua dịch vụ dự phòng - trước đây chỉ có video.",
          "Sửa lỗi một số video TikTok có hình nhưng không có tiếng trên iPhone/Mac: âm thanh của chúng là MP3 nằm trong video, mà trình phát của Apple không phát được. Giờ app tự đổi sang AAC (hình giữ nguyên).",
          "Sửa lỗi \"The request is not allowed…\" khi lưu một lô lớn về iPhone: các tệp giờ được chuẩn bị sẵn trước khi bạn bấm nút lưu.",
          "Các dòng đã tải xong có thể tick lại, và bấm vào ô checkbox hoặc cả dòng đều chọn được. Nút lưu đổi tên thành \"Lưu về máy\" và cũng hiện cạnh nút Tải tất cả.",
          "Sau khi lưu về máy, bạn nhận được thông báo xác nhận. Mọi nút hành động giờ có cùng kích thước, và mỗi dòng tải xuống hiển thị gọn trên điện thoại.",
        ],
      },
      {
        date: "25-09-2026",
        title: "Chuyển nhanh English ⇄ Tiếng Việt",
        items: [
          "Thêm nút chuyển EN | VI ở đầu mọi trang — không cần vào Cài đặt nữa. Máy đặt ngôn ngữ tiếng Việt thì app tự mở bằng tiếng Việt.",
          "Thông báo lỗi từ server (không đọc được link, tài khoản private, thiếu FFmpeg…) giờ theo đúng ngôn ngữ đã chọn thay vì luôn là tiếng Việt.",
          "Trang đăng nhập của bản cloud cũng được dịch, có link đổi English / Tiếng Việt riêng.",
          "Sửa lỗi thanh menu phía trên bị cắt trên điện thoại — các mục giờ xuống dòng nên không còn mục nào bị khuất.",
          "Dịch nốt những chỗ tiếng Anh còn sót (\"Nền tảng được hỗ trợ\", lỗi kết nối).",
        ],
      },
      {
        date: "25-09-2026",
        title: "Tải Facebook trên server cloud không còn bị treo",
        items: [
          "Sửa lỗi tải Facebook trên server cloud bị kẹt ở \"100%\" hàng phút và làm chậm mọi request khác. Một số video Facebook chỉ có chất lượng cao nhất ở dạng AV1, server phải re-encode sang H.264 trên CPU rất yếu — giờ nó lấy luôn bản H.264 có sẵn của Facebook.",
          "Đánh đổi: trên server cloud, video Facebook mà bản 1080p chỉ có ở dạng AV1 sẽ tải bản 720p H.264. Bản desktop giữ nguyên.",
          "Khi tải xong 100% nhưng vẫn đang xử lý, thanh tiến trình hiện \"Đang xử lý video…\" thay vì trông như bị đơ.",
        ],
      },
      {
        date: "18-09-2026",
        title: "Sửa lỗi TikTok và độ ổn định khi tải",
        items: [
          "Sửa lỗi thumbnail của bài TikTok Photo Mode/carousel hiển thị sai với một số bài.",
          "Sửa nút \"Retry\" khi tải lỗi đôi khi báo lỗi 404 thay vì tải lại được.",
          "Sửa lỗi lưu hàng loạt ảnh/video vào Photos trên iPhone — trước đây chỉ item đầu tiên được lưu.",
        ],
      },
      {
        date: "16-09-2026",
        title: "Sửa YouTube, thêm API token, lưu qua Share Sheet",
        items: [
          "Sửa lỗi tải YouTube bị chặn sau khi YouTube áp dụng giao thức chống bot mới (SABR).",
          "Thêm xác thực bằng API token (Bearer) — ViDrop giờ tự động hoá được từ app/thiết bị khác (như iOS Shortcut mới bên dưới) mà không cần đăng nhập qua trình duyệt mỗi lần.",
          "Share link từ Instagram/TikTok/... thẳng vào ViDrop trên điện thoại (qua Share Sheet) giờ tự lưu kết quả, kể cả lưu hàng loạt.",
          "Mới: hướng dẫn cài iOS Shortcut — build 1 lần để iPhone nào cũng gửi link thẳng tới server ViDrop và nhận lại file, không cần mở trình duyệt.",
          "Khoá quyền quản trị SSH từ xa lại sau cổng mua hàng (IAP) của app, đóng một đường truy cập lẽ ra không nên mở.",
        ],
      },
      {
        date: "29-08-2026 → 10-09-2026",
        title: "Truy cập từ xa: dùng ViDrop ngay trên điện thoại",
        items: [
          "Thêm Remote Web Access — chạy ViDrop trên server cloud riêng và truy cập an toàn từ điện thoại hoặc thiết bị khác qua URL riêng, có cổng đăng nhập/trust-cookie bảo vệ.",
          "Tải hàng loạt (playlist, carousel) qua remote access giờ gộp lại thành 1 file ZIP duy nhất để tải về một lần.",
          "Đồng bộ session đăng nhập Instagram/Threads từ Mac lên server cloud, nên tải có xác thực vẫn chạy được kể cả khi ViDrop không chạy trên máy của mày.",
          "Thêm tuỳ chọn upload cookies.txt thủ công cho server headless/cloud không có trình duyệt để tự lấy cookie.",
          "Sửa lỗi không tìm thấy ffmpeg trên server cloud chạy Linux.",
        ],
      },
      {
        date: "29-08-2026 → 30-08-2026",
        title: "TikTok Photo Mode + fallback thông minh hơn",
        items: [
          "Thêm hỗ trợ tải bài TikTok \"Photo Mode\" (slideshow nhiều ảnh) — trước đây hoàn toàn chưa hỗ trợ.",
          "Sửa lỗi tải video TikTok bị hỏng sau khi TikTok đổi hệ thống — giờ tự động chuyển sang cách tải khác khi cách chính không chạy được.",
          "Sửa lỗi tải video LinkedIn.",
          "Build lại ffmpeg đi kèm thành bản arm64 gốc cho Apple Silicon, tăng tốc thật trên Mac M-series (trước đây chạy qua giả lập Rosetta 2).",
          "Xử lý lỗi chặt hơn để check/tải lỗi không bao giờ hiện thông báo kỹ thuật khó hiểu.",
        ],
      },
      {
        date: "10-07-2026",
        title: "Sửa Instagram/Threads, thêm chẩn đoán tự phục vụ",
        items: [
          "Sửa tận gốc lỗi check/tải không chạy được trên máy Mac mới cài (đường dẫn SSL certificate trong app bị hỏng).",
          "Sửa lỗi đọc cookie Chrome có thể bỏ sót session Instagram/Threads vừa đăng nhập.",
          "Sửa thông báo \"Private account\" gây hiểu lầm khi nguyên nhân thật là session hết hạn.",
          "Thêm mục Diagnostic Logs và Reset App Data trong Cài đặt để tự chẩn đoán và báo lỗi.",
          "Dán nguyên đoạn \"Share\" (tiêu đề, hashtag...) của nền tảng giờ cũng lấy được link, không cần link trần.",
          "Chỉnh giao diện khớp pixel với thiết kế Figma (màu logo, khoảng cách, độ tương phản).",
        ],
      },
    ],
  },
};

export const translations: Record<Language, Translations> = { en, vi };
