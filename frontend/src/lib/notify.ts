// System notifications for finished downloads, used only when the tab is in
// the background; while the tab is visible the in-page toast is enough.
// Everything here degrades silently: no Notification API, an insecure context,
// a denied permission or a constructor that throws all just mean "no system
// notification", never an error shown to the user.

const supported = (): boolean =>
  typeof window !== "undefined" && "Notification" in window && window.isSecureContext !== false;

// Ask at most once per page load, and only while the permission is still
// undecided. Call it from a user's click on a Download button, never on load.
let asked = false;
export const requestNotifyPermission = (): void => {
  if (asked || !supported() || Notification.permission !== "default") return;
  asked = true;
  try {
    const result: unknown = Notification.requestPermission();
    if (result instanceof Promise) result.catch(() => undefined);
  } catch {
    // Some browsers throw outside a gesture or in embedded views: stay silent.
  }
};

// Test hook: forget that we asked.
export const resetNotifyPermissionAsked = (): void => {
  asked = false;
};

// Shows one system notification when the tab is hidden and permission was
// granted. Returns whether it fired. Clicking it brings the tab back.
export const notifyIfHidden = (title: string, body: string): boolean => {
  if (!supported() || !document.hidden || Notification.permission !== "granted") return false;
  try {
    const notification = new Notification(title, { body, tag: "vidrop-download" });
    notification.onclick = () => {
      window.focus();
      notification.close();
    };
    return true;
  } catch {
    return false;
  }
};

// "very-long-name-of-a-file.mp4" -> "very-long-na…file.mp4": keeps the start
// and the end (where the extension is), cuts the middle.
export const truncateMiddle = (text: string, max = 36): string => {
  if (text.length <= max) return text;
  const keep = max - 1;
  const tail = Math.ceil(keep * 0.4);
  const head = keep - tail;
  return `${text.slice(0, head)}…${text.slice(text.length - tail)}`;
};
