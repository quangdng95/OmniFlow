import { motion } from "framer-motion";
import Logo from "./Logo";
import type { Page } from "./Header";
import { useLanguage } from "../i18n/LanguageContext";

interface FooterProps {
  onNavigate: (page: Page) => void;
}

// Terms live here (not in the page body): a link on the left, the byline on the right.
const Footer = ({ onNavigate }: FooterProps) => {
  const { t } = useLanguage();
  return (
    <motion.footer
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className="page-container flex flex-wrap items-center justify-between gap-x-6 gap-y-2 pt-6 pb-4"
    >
      <button
        type="button"
        onClick={() => onNavigate("terms")}
        className="inline-flex min-h-11 cursor-pointer items-center bg-transparent px-0 text-base font-bold text-ink underline underline-offset-4"
      >
        {t.header.nav.terms}
      </button>
      <div className="flex items-center gap-2">
        <p className="m-0 text-base text-ink-muted">{t.footer.by}</p>
        <Logo size="small" />
      </div>
    </motion.footer>
  );
};

export default Footer;
