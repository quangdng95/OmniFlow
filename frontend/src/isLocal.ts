// True when this page is being viewed from the same machine that's running
// server.py (desktop app, or a browser tab on localhost) - false for a
// remote visitor on a shared/tunnelled deployment. Native file/folder
// dialogs, server-side clipboard reads, and Instagram cookies only make
// sense in the local case; see server.py's is_local_request for the
// matching backend-side check. A function (not a precomputed constant) so
// tests can override window.location.hostname without needing to reset and
// re-import modules.
export const isLocal = () =>
  window.location.hostname === "127.0.0.1" || window.location.hostname === "localhost";

// A phone/tablet (touch-first) visiting a remote deployment: the flow there is
// paste -> auto-download -> "Save to device", with no manual download step.
// A function for the same test-override reason as isLocal.
export const isMobileRemote = () =>
  !isLocal() &&
  (/Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent) ||
    (navigator.maxTouchPoints > 1 && /Mac/i.test(navigator.platform)));
