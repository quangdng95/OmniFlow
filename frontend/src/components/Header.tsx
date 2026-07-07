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
          {navItems.map((item) => {
            const isActive = active === item.key;
            return (
              <Button
                key={item.key}
                type="text"
                aria-current={isActive ? "page" : undefined}
                style={{
                  color: isActive ? "#0d9585" : "rgba(31, 41, 55, 0.65)",
                  fontWeight: isActive ? 600 : 500,
                  borderBottom: isActive ? "2px solid #0d9585" : "2px solid transparent",
                  borderRadius: 0,
                  padding: "0 4px",
                  height: 36,
                  transition: "all 0.2s ease",
                }}
                onClick={() => onNavigate(item.key)}
              >
                {item.label}
              </Button>
            );
          })}
        </div>

        <Divider style={{ borderColor: "rgba(0,0,0,0.06)", margin: 0 }} />

        <Logo size="large" />

        <div style={{ display: "flex", flexDirection: "column", gap: 16, color: "#1f2937" }}>
          <h1 className="omniflow-heading-title" style={{ margin: 0, fontSize: 24, fontWeight: 600, lineHeight: "32px", color: "#1f2937" }}>
            {t.header[active].title}
          </h1>
          {active === "home" && (
            <div style={{ fontSize: 14, lineHeight: "20px", color: "rgba(31, 41, 55, 0.75)" }}>
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
