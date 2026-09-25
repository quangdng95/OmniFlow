import type { Language } from "./translations";

export const LANGUAGE_STORAGE_KEY = "omniflow-language";
// Same cookie name remote_web's server-rendered /unlock page reads and writes,
// so a language picked there carries into the app and the other way round.
const LANGUAGE_COOKIE = "omniflow-language";
const COOKIE_MAX_AGE_SECONDS = 365 * 24 * 60 * 60;

const isLanguage = (value: unknown): value is Language => value === "en" || value === "vi";

const readCookie = (): string | null => {
  try {
    const match = document.cookie.match(new RegExp(`(?:^|;\\s*)${LANGUAGE_COOKIE}=([^;]*)`));
    return match ? decodeURIComponent(match[1]) : null;
  } catch {
    return null;
  }
};

// An explicit earlier choice wins (localStorage, then the shared cookie);
// otherwise follow the browser - a Vietnamese device starts in Vietnamese.
export const detectLanguage = (): Language => {
  try {
    const stored = localStorage.getItem(LANGUAGE_STORAGE_KEY);
    if (isLanguage(stored)) return stored;
  } catch {
    // localStorage can throw (private mode, blocked site data) - fall through.
  }
  const fromCookie = readCookie();
  if (isLanguage(fromCookie)) return fromCookie;
  const browser = typeof navigator === "undefined" ? "" : navigator.language ?? "";
  return browser.toLowerCase().startsWith("vi") ? "vi" : "en";
};

export const persistLanguage = (language: Language): void => {
  try {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
  } catch {
    // Persisting is best-effort; the choice still applies for this session.
  }
  try {
    document.cookie = `${LANGUAGE_COOKIE}=${language}; path=/; max-age=${COOKIE_MAX_AGE_SECONDS}; SameSite=Lax`;
    document.documentElement.lang = language;
  } catch {
    // No document (non-browser test environment) - nothing to update.
  }
};
