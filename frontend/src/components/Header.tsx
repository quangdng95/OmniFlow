import { Check, FileText, History, Home, Menu, ScrollText, Settings as SettingsIcon, Smartphone } from "lucide-react";
import type { ComponentType } from "react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import Logo from "./Logo";
import LanguageSwitcher from "./LanguageSwitcher";
import { useLanguage } from "../i18n/LanguageContext";
import { isLocal } from "../isLocal";

export type Page = "home" | "history" | "settings" | "terms" | "shortcut" | "changelog";

interface HeaderProps {
  active: Page;
  onNavigate: (page: Page) => void;
}

interface NavItem {
  key: Page;
  label: string;
  icon: ComponentType<{ className?: string }>;
}

// One slim, sticky bar: logo (also the way back Home), language switch, and a
// single menu button that holds every page. It used to be ~340px tall on a
// phone (41% of the screen) with six nav pills, the language switch and a big
// logo stacked in rows, and it scrolled away.
const Header = ({ active, onNavigate }: HeaderProps) => {
  const { t } = useLanguage();

  const navItems: NavItem[] = [
    { key: "home", label: t.header.nav.home, icon: Home },
    { key: "history", label: t.header.nav.history, icon: History },
    { key: "changelog", label: t.header.nav.changelog, icon: ScrollText },
    { key: "settings", label: t.header.nav.settings, icon: SettingsIcon },
    { key: "terms", label: t.header.nav.terms, icon: FileText },
    // The Shortcut only makes sense against a remote deployment (it calls
    // /api/* with a Bearer token, which only the remote_web trust gate
    // understands) - hidden for the local desktop app, same convention as
    // Settings' Target Path/Instagram Cookies sections hiding in remote mode.
    ...(isLocal() ? [] : [{ key: "shortcut" as Page, label: t.header.nav.shortcut, icon: Smartphone }]),
  ];

  return (
    <header className="sticky top-0 z-40 w-full bg-background">
      <div className="page-container">
      <div className="flex min-h-16 items-center justify-between gap-3 border-b-[3px] border-ink">
        <button
          type="button"
          onClick={() => onNavigate("home")}
          aria-label={t.header.nav.home}
          className="flex min-h-11 select-none items-center"
        >
          <Logo size="compact" />
        </button>

        <div className="flex items-center gap-1.5">
          <LanguageSwitcher />
          <DropdownMenu>
            <DropdownMenuTrigger
              render={
                <button
                  type="button"
                  aria-label={t.header.menu}
                  className="box-border inline-flex select-none h-(--control-h) min-w-11 cursor-pointer items-center justify-center gap-2 border-[3px] border-ink bg-transparent px-2.5 font-display text-base font-bold text-ink uppercase hover:bg-ink hover:text-on-ink aria-expanded:bg-ink aria-expanded:text-on-ink sm:px-3.5"
                />
              }
            >
              <Menu className="h-5 w-5" aria-hidden />
              <span className="hidden sm:inline" aria-hidden>
                {t.header.menu}
              </span>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56 min-w-56 border-[3px] border-ink p-0 shadow-hard ring-0">
              {navItems.map(({ key, label, icon: Icon }) => {
                const isActive = active === key;
                return (
                  <DropdownMenuItem
                    key={key}
                    onClick={() => onNavigate(key)}
                    aria-current={isActive ? "page" : undefined}
                    className={cn(
                      "min-h-11 cursor-pointer gap-2.5 px-3.5 text-base",
                      isActive && "font-bold text-brand focus:text-ink"
                    )}
                  >
                    <Icon className="h-5 w-5" aria-hidden />
                    <span className="flex-1">{label}</span>
                    {isActive && <Check className="h-5 w-5" aria-hidden />}
                  </DropdownMenuItem>
                );
              })}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
      </div>
    </header>
  );
};

export default Header;
