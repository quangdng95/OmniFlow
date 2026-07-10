import { Button } from "@/components/ui/button";
import { motion } from "framer-motion";
import Logo from "./Logo";
import { useLanguage } from "../i18n/LanguageContext";

export type Page = "home" | "settings" | "terms";

interface HeaderProps {
  active: Page;
  onNavigate: (page: Page) => void;
}

const Header = ({ active, onNavigate }: HeaderProps) => {
  const { t } = useLanguage();

  const navItems: { key: Page; label: string }[] = [
    { key: "home", label: t.header.nav.home },
    { key: "settings", label: t.header.nav.settings },
    { key: "terms", label: t.header.nav.terms },
  ];

  return (
    <motion.div
      className="w-full bg-[#fbfbf9] border-b border-neutral-200/40 shadow-md flex justify-center py-4 px-6 select-none"
      initial={{ opacity: 0, y: -16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
    >
      <div className="w-full flex flex-col gap-4 items-center">
        {/* Navigation */}
        <div className="w-full max-w-[680px] flex gap-6 items-center justify-center">
          {navItems.map((item) => {
            const isActive = active === item.key;
            return (
              <Button
                key={item.key}
                variant={isActive ? "default" : "secondary"}
                size="sm"
                className={`font-medium ${
                  isActive
                    ? "bg-[#171717] text-[#fafafa] shadow-sm"
                    : "bg-[#f5f5f5] text-[#171717] hover:bg-neutral-200"
                }`}
                onClick={() => onNavigate(item.key)}
              >
                {item.label}
              </Button>
            );
          })}
        </div>

        {/* Divider - full-bleed, spans the header's true width (not capped to the 680px content column) */}
        <div className="w-full h-px bg-neutral-200" />

        {/* Logo, Title & Description (Home Page Only) */}
        {active === "home" && (
          <div className="w-full max-w-[680px] flex flex-col gap-4 items-center">
            <Logo size="large" />
            <div className="flex flex-col gap-2 items-center text-center select-none">
              <h1 className="font-semibold text-xl text-[#334155] leading-snug">
                {t.header.home.title}
              </h1>
              <div className="text-sm font-light text-neutral-500 leading-relaxed whitespace-pre-line max-w-[480px]">
                {t.header.home.descriptionLine1} {t.header.home.descriptionLine2}
              </div>
            </div>
          </div>
        )}
      </div>
    </motion.div>
  );
};

export default Header;
