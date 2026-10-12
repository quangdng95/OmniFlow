import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import CheckingStatusCard from "./CheckingStatusCard";
import { LanguageProvider } from "../i18n/LanguageContext";

const renderCard = (props: Partial<React.ComponentProps<typeof CheckingStatusCard>> = {}) => {
  const onCancel = vi.fn();
  render(
    <LanguageProvider>
      <CheckingStatusCard seconds={3} onCancel={onCancel} {...props} />
    </LanguageProvider>
  );
  return onCancel;
};

describe("CheckingStatusCard", () => {
  it("announces progress as a status with the elapsed seconds", () => {
    renderCard({ seconds: 7 });
    expect(screen.getByRole("status")).toHaveTextContent("Checking Link… (7s)");
  });

  it("lets the user cancel", async () => {
    const onCancel = renderCard();
    await userEvent.setup().click(screen.getByRole("button", { name: "Cancel" }));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("shows the Keychain hint only when asked to", () => {
    renderCard();
    expect(screen.queryByText(/Keychain/)).not.toBeInTheDocument();
  });

  it("explains the Keychain prompt for Instagram/Threads", () => {
    renderCard({ showKeychainHint: true });
    expect(screen.getByText(/Keychain/)).toBeInTheDocument();
  });
});
