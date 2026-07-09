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
      className="flex gap-2 items-end justify-center w-full pt-6 pb-2"
    >
      <p
        className="text-xs text-slate-900 whitespace-nowrap m-0"
        style={{ textShadow: "0px 2px 4px rgba(0,0,0,0.02), 0px 1px 6px rgba(0,0,0,0.02), 0px 1px 2px rgba(0,0,0,0.03)" }}
      >
        {t.footer.by}
      </p>
      <Logo size="small" />
    </motion.div>
  );
};

export default Footer;
