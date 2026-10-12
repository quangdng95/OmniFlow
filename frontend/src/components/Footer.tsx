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
      <p className="m-0 whitespace-nowrap text-xs text-muted-foreground">
        {t.footer.by}
      </p>
      <Logo size="small" />
    </motion.div>
  );
};

export default Footer;
