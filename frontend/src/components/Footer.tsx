import { motion } from "framer-motion";
import Logo from "./Logo";
import { useLanguage } from "../i18n/LanguageContext";

const Footer = () => {
  const { t } = useLanguage();
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      style={{
        display: "flex",
        gap: 8,
        alignItems: "center",
        justifyContent: "center",
        width: "100%",
        padding: "24px 0 8px",
      }}
    >
      <span style={{ fontSize: 12, color: "rgba(26,26,26,0.92)" }}>{t.footer.by}</span>
      <Logo size="small" />
    </motion.div>
  );
};

export default Footer;
