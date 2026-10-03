import { type Page } from "./Header";
import { useLanguage } from "../i18n/LanguageContext";

interface PageTitleProps {
  page: Exclude<Page, "home">;
}

// The title that used to live inside the (tall) header on every non-Home page.
// The header is now a single slim bar, so the page's name sits at the top of
// its own content instead.
const PageTitle = ({ page }: PageTitleProps) => {
  const { t } = useLanguage();
  const titles: Record<Exclude<Page, "home">, string> = {
    history: t.header.history.title,
    settings: t.header.settings.title,
    terms: t.header.terms.title,
    shortcut: t.header.shortcut.title,
    changelog: t.header.changelog.title,
  };
  return <h2 className="m-0 text-xl font-bold text-slate-800 select-none">{titles[page]}</h2>;
};

export default PageTitle;
