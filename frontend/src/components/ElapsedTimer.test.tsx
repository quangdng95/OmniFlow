import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ElapsedTimer from "./ElapsedTimer";
import { formatElapsed } from "../lib/formatElapsed";

describe("formatElapsed", () => {
  it("formats m:ss and h:mm:ss", () => {
    expect(formatElapsed(0)).toBe("0:00");
    expect(formatElapsed(7)).toBe("0:07");
    expect(formatElapsed(65)).toBe("1:05");
    expect(formatElapsed(750)).toBe("12:30");
    expect(formatElapsed(3600)).toBe("1:00:00");
    expect(formatElapsed(3725)).toBe("1:02:05");
  });
});

describe("ElapsedTimer", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("starts at 0:00 and shows 1:05 after 65 seconds", () => {
    render(<ElapsedTimer label="Time elapsed" />);
    expect(screen.getByRole("timer")).toHaveTextContent("0:00");
    act(() => {
      vi.advanceTimersByTime(65_000);
    });
    expect(screen.getByRole("timer")).toHaveTextContent("1:05");
  });

  it("is not a live region, so it is not re-read every second", () => {
    render(<ElapsedTimer label="Time elapsed" />);
    expect(screen.getByRole("timer")).toHaveAttribute("aria-live", "off");
  });

  it("follows the wall clock when ticks are throttled", () => {
    render(<ElapsedTimer label="Time elapsed" />);
    act(() => {
      vi.setSystemTime(Date.now() + 30_000); // tab slept: clock jumped
      vi.advanceTimersByTime(1000);
    });
    expect(screen.getByRole("timer")).toHaveTextContent("0:31");
  });

  it("leaves no timer running after unmount", () => {
    const { unmount } = render(<ElapsedTimer label="Time elapsed" />);
    expect(vi.getTimerCount()).toBe(1);
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });
});
