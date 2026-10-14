// "Clear cache and saved data": wipes everything this browser (or the Mac app's web view) keeps for ViDrop,
// so nobody has to dig through the system's Safari/Chrome settings. It cannot reach the browser's own HTTP
// cache or the Home Screen icon iOS already copied; instead it re-downloads the core files so those caches
// hold the current ones, and reloads the page with a fresh URL.

// Files worth refreshing in the HTTP cache. The ?v= matches the links in index.html.
const CORE_URLS = ["/", "/manifest.webmanifest?v=4", "/apple-touch-icon.png?v=4", "/favicon.ico?v=4", "/favicon.svg?v=4"];

export interface ClearReport {
  storageKeys: number;
  cacheStores: number;
  cookies: number;
}

const attempt = async (work: () => void | Promise<void>): Promise<void> => {
  try {
    await work();
  } catch {
    // One storage being blocked (private mode, a policy) must not stop the others.
  }
};

const expireVisibleCookies = (): number => {
  const names = document.cookie
    .split(";")
    .map((part) => part.split("=")[0].trim())
    .filter(Boolean);
  const host = window.location.hostname;
  for (const name of names) {
    for (const domain of ["", `; domain=${host}`, `; domain=.${host}`]) {
      document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/${domain}`;
    }
  }
  return names.length;
};

export async function clearBrowserData(): Promise<ClearReport> {
  const report: ClearReport = { storageKeys: 0, cacheStores: 0, cookies: 0 };

  // Make the HTTP cache hold the current core files before anything else is dropped.
  await attempt(async () => {
    await Promise.allSettled(CORE_URLS.map((url) => fetch(url, { cache: "reload", credentials: "same-origin" })));
  });

  await attempt(() => {
    report.storageKeys += window.localStorage.length;
    window.localStorage.clear();
  });
  await attempt(() => {
    report.storageKeys += window.sessionStorage.length;
    window.sessionStorage.clear();
  });
  await attempt(async () => {
    if (typeof caches === "undefined") return;
    const names = await caches.keys();
    await Promise.all(names.map((name) => caches.delete(name)));
    report.cacheStores = names.length;
  });
  await attempt(async () => {
    if (!("serviceWorker" in navigator)) return;
    const registrations = await navigator.serviceWorker.getRegistrations();
    await Promise.all(registrations.map((registration) => registration.unregister()));
  });
  await attempt(async () => {
    const factory = indexedDB as IDBFactory & { databases?: () => Promise<IDBDatabaseInfo[]> };
    if (typeof factory.databases !== "function") return;
    const databases = await factory.databases();
    await Promise.all(
      databases.map(
        (database) =>
          new Promise<void>((resolve) => {
            if (!database.name) return resolve();
            const request = indexedDB.deleteDatabase(database.name);
            request.onsuccess = request.onerror = request.onblocked = () => resolve();
          })
      )
    );
  });
  await attempt(() => {
    report.cookies = expireVisibleCookies();
  });
  return report;
}

// A fresh URL so the page itself is not served from a cached copy.
export const reloadFresh = (): void => {
  window.location.replace(`/?fresh=${Date.now()}`);
};
