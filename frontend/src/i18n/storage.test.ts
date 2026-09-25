import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { detectLanguage, LANGUAGE_STORAGE_KEY, persistLanguage } from "./storage";

const setBrowserLanguage = (value: string) => {
  vi.spyOn(window.navigator, "language", "get").mockReturnValue(value);
};

const clearLanguageCookie = () => {
  document.cookie = "omniflow-language=; path=/; max-age=0";
};

describe("language detection", () => {
  beforeEach(() => {
    localStorage.clear();
    clearLanguageCookie();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("starts in Vietnamese on a Vietnamese browser when nothing was chosen before", () => {
    setBrowserLanguage("vi-VN");
    expect(detectLanguage()).toBe("vi");
  });

  it("starts in English on any other browser language", () => {
    setBrowserLanguage("fr-FR");
    expect(detectLanguage()).toBe("en");
    setBrowserLanguage("en-US");
    expect(detectLanguage()).toBe("en");
  });

  it("an explicit earlier choice beats the browser language", () => {
    setBrowserLanguage("vi-VN");
    localStorage.setItem(LANGUAGE_STORAGE_KEY, "en");
    expect(detectLanguage()).toBe("en");
  });

  it("falls back to the shared cookie (set by the server's /unlock page) before the browser language", () => {
    setBrowserLanguage("en-US");
    document.cookie = "omniflow-language=vi; path=/";
    expect(detectLanguage()).toBe("vi");
  });

  it("ignores a junk stored value instead of trusting it", () => {
    setBrowserLanguage("en-US");
    localStorage.setItem(LANGUAGE_STORAGE_KEY, "klingon");
    document.cookie = "omniflow-language=<script>; path=/";
    expect(detectLanguage()).toBe("en");
  });

  it("still works when localStorage throws (private mode / blocked site data)", () => {
    setBrowserLanguage("vi");
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(detectLanguage()).toBe("vi");
  });
});

describe("persistLanguage", () => {
  beforeEach(() => {
    localStorage.clear();
    clearLanguageCookie();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("saves the choice to localStorage, the shared cookie, and <html lang>", () => {
    persistLanguage("vi");
    expect(localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe("vi");
    expect(document.cookie).toContain("omniflow-language=vi");
    expect(document.documentElement.lang).toBe("vi");
  });

  it("does not throw when localStorage refuses writes", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("quota");
    });
    expect(() => persistLanguage("en")).not.toThrow();
    expect(document.documentElement.lang).toBe("en");
  });
});
