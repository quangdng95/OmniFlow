import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { notifyIfHidden, requestNotifyPermission, resetNotifyPermissionAsked, truncateMiddle } from "./notify";

type Perm = "default" | "granted" | "denied";

const install = (permission: Perm, hidden: boolean) => {
  const instances: { title: string; options?: NotificationOptions; onclick: (() => void) | null; close: () => void }[] = [];
  const requestPermission = vi.fn().mockResolvedValue("granted");
  class MockNotification {
    static permission: Perm = permission;
    static requestPermission = requestPermission;
    onclick: (() => void) | null = null;
    close = vi.fn();
    title: string;
    options?: NotificationOptions;
    constructor(title: string, options?: NotificationOptions) {
      this.title = title;
      this.options = options;
      instances.push(this);
    }
  }
  vi.stubGlobal("Notification", MockNotification);
  Object.defineProperty(document, "hidden", { configurable: true, get: () => hidden });
  Object.defineProperty(window, "isSecureContext", { configurable: true, value: true });
  return { instances, requestPermission, MockNotification };
};

describe("notify", () => {
  beforeEach(() => resetNotifyPermissionAsked());
  afterEach(() => {
    vi.unstubAllGlobals();
    Object.defineProperty(document, "hidden", { configurable: true, get: () => false });
  });

  it("fires exactly one notification when granted and the tab is hidden", () => {
    const { instances } = install("granted", true);
    expect(notifyIfHidden("Saved", "a.mp4")).toBe(true);
    expect(instances).toHaveLength(1);
    expect(instances[0].title).toBe("Saved");
    expect(instances[0].options?.body).toBe("a.mp4");
  });

  it("does not fire while the tab is visible (the toast covers it)", () => {
    const { instances } = install("granted", false);
    expect(notifyIfHidden("Saved", "a.mp4")).toBe(false);
    expect(instances).toHaveLength(0);
  });

  it.each<Perm>(["denied", "default"])("does not fire when permission is %s", (perm) => {
    const { instances } = install(perm, true);
    expect(notifyIfHidden("Saved", "a.mp4")).toBe(false);
    expect(instances).toHaveLength(0);
  });

  it("is silent when the Notification API is missing", () => {
    vi.stubGlobal("Notification", undefined);
    // `"Notification" in window` is still true for an undefined stub, so remove it properly.
    delete (window as unknown as Record<string, unknown>).Notification;
    expect(notifyIfHidden("Saved", "a.mp4")).toBe(false);
    expect(() => requestNotifyPermission()).not.toThrow();
  });

  it("is silent outside a secure context", () => {
    const { instances } = install("granted", true);
    Object.defineProperty(window, "isSecureContext", { configurable: true, value: false });
    expect(notifyIfHidden("Saved", "a.mp4")).toBe(false);
    expect(instances).toHaveLength(0);
  });

  it("is silent when the constructor throws", () => {
    install("granted", true);
    vi.stubGlobal("Notification", Object.assign(function () { throw new Error("nope"); }, { permission: "granted" }));
    expect(notifyIfHidden("Saved", "a.mp4")).toBe(false);
  });

  it("focuses the tab and closes the notification when clicked", () => {
    const { instances } = install("granted", true);
    const focus = vi.spyOn(window, "focus").mockImplementation(() => undefined);
    notifyIfHidden("Saved", "a.mp4");
    instances[0].onclick?.();
    expect(focus).toHaveBeenCalled();
    expect(instances[0].close).toHaveBeenCalled();
  });

  it("asks for permission only while undecided, and only once", () => {
    const { requestPermission } = install("default", false);
    requestNotifyPermission();
    requestNotifyPermission();
    expect(requestPermission).toHaveBeenCalledTimes(1);
  });

  it.each<Perm>(["granted", "denied"])("never asks when permission is already %s", (perm) => {
    const { requestPermission } = install(perm, false);
    requestNotifyPermission();
    expect(requestPermission).not.toHaveBeenCalled();
  });

  it("swallows a rejected permission request", async () => {
    const { requestPermission } = install("default", false);
    requestPermission.mockRejectedValue(new Error("blocked"));
    expect(() => requestNotifyPermission()).not.toThrow();
    await Promise.resolve();
  });
});

describe("truncateMiddle", () => {
  it("leaves short names alone", () => {
    expect(truncateMiddle("a.mp4")).toBe("a.mp4");
  });
  it("cuts the middle and keeps the extension", () => {
    const out = truncateMiddle("a-very-long-video-title-that-goes-on-and-on-forever.mp4", 24);
    expect(out).toHaveLength(24);
    expect(out).toContain("…");
    expect(out.endsWith(".mp4")).toBe(true);
    expect(out.startsWith("a-very-long")).toBe(true);
  });
});
