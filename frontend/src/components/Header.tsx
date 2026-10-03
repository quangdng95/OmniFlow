import { Check, FileText, History, Home, Menu, ScrollText, Settings as SettingsIcon, Smartphone } from "lucide-react";
import type { ComponentType } from "react";
import { Button } from "@/components/ui/button";
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
    <header className="sticky top-0 z-40 w-full border-b border-neutral-200/70 bg-[#fbfbf9]/90 backdrop-blur-md select-none">
      <div className="mx-auto flex h-12 w-full max-w-[680px] items-center justify-between gap-3 px-4">
        <button
          type="button"
          onClick={() => onNavigate("home")}
          aria-label={t.header.nav.home}
          className="rounded-md outline-none focus-visible:ring-2 focus-visible:ring-[#0d9585]/50"
        >
          <Logo size="compact" />
        </button>

        <div className="flex items-center gap-2">
          <LanguageSwitcher />
          <DropdownMenu>
            <DropdownMenuTrigger
              render={
                <Button variant="outline" size="icon" aria-label={t.header.menu} className="border-neutral-200 bg-white shadow-none" />
              }
            >
              <Menu className="h-4 w-4" />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-52 min-w-52 p-1.5">
              {navItems.map(({ key, label, icon: Icon }) => {
                const isActive = active === key;
                return (
                  <DropdownMenuItem
                    key={key}
                    onClick={() => onNavigate(key)}
                    aria-current={isActive ? "page" : undefined}
                    className={cn("gap-2.5 px-2.5 py-2 text-sm", isActive && "font-semibold text-[#0d9585]")}
                  >
                    <Icon className="h-4 w-4" />
                    <span className="flex-1">{label}</span>
                    {isActive && <Check className="h-4 w-4" />}
                  </DropdownMenuItem>
                );
              })}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  );
};

export default Header;
