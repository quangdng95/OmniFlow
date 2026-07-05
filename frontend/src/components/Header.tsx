import { Button, Divider } from "antd";
import { motion } from "framer-motion";
import Logo from "./Logo";
import { HEADER_BG } from "../theme";
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
      className="omniflow-header"
      initial={{ opacity: 0, y: -16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      style={{ background: HEADER_BG }}
    >
      <div className="omniflow-header-inner">
        <div className="omniflow-nav" style={{ display: "flex", gap: 24 }}>
          {navItems.map((item) => (
            <Button
              key={item.key}
              type="text"
              aria-current={active === item.key ? "page" : undefined}
              style={{ color: "white", padding: 0, height: 36 }}
              onClick={() => onNavigate(item.key)}
            >
              {item.label}
            </Button>
          ))}
        </div>

        <Divider style={{ borderColor: "rgba(255,255,255,0.2)", margin: 0 }} />

        <Logo size="large" />

        <div style={{ display: "flex", flexDirection: "column", gap: 16, color: "white" }}>
          <h1 className="omniflow-heading-title" style={{ margin: 0, fontSize: 24, fontWeight: 600, lineHeight: "32px" }}>
            {t.header[active].title}
          </h1>
          {active === "home" && (
            <div style={{ fontSize: 14, lineHeight: "20px" }}>
              {t.header.home.descriptionLine1} <br />
              {t.header.home.descriptionLine2}
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
};

export default Header;
