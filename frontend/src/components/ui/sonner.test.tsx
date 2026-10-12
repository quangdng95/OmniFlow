import { act, render, screen, waitFor } from "@testing-library/react";
import { toast } from "sonner";
import { afterEach, describe, expect, it } from "vitest";
import { LanguageProvider } from "../../i18n/LanguageContext";
import { translations } from "../../i18n/translations";

const renderWith = (lang: "en" | "vi") => {
  localStorage.setItem("omniflow-language", lang);
  return render(
    <LanguageProvider>
      <div />
    </LanguageProvider>
  );
};

describe("toast close button", () => {
  afterEach(() => {
    act(() => {
      toast.dismiss();
    });
    localStorage.clear();
  });

  it.each([
    ["en", "Close notification"],
    ["vi", "Đóng thông báo"],
  ] as const)("is present on every toast type with the %s label", async (lang, label) => {
    renderWith(lang);
    act(() => {
      toast.success("Saved");
      toast.error("Failed");
      toast.info("FYI");
    });
    await waitFor(() => expect(screen.getAllByRole("button", { name: label })).toHaveLength(3));
  });

  it("closes the toast when pressed", async () => {
    renderWith("en");
    act(() => {
      toast.success("Saved to your device");
    });
    const button = await screen.findByRole("button", { name: "Close notification" });
    act(() => button.click());
    await waitFor(() => expect(button.closest("[data-sonner-toast]")?.getAttribute("data-removed")).toBe("true"));
  });

  it("has the label in both languages in the catalog", () => {
    expect(translations.en.toast.close).toBe("Close notification");
    expect(translations.vi.toast.close).toBe("Đóng thông báo");
  });
});
