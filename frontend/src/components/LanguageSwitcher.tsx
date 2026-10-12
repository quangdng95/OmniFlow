import { cn } from "@/lib/utils";
import { useLanguage } from "../i18n/LanguageContext";
import type { Language } from "../i18n/translations";

const OPTIONS: { value: Language; short: string }[] = [
  { value: "en", short: "EN" },
  { value: "vi", short: "VI" },
];

const LanguageSwitcher = () => {
  const { t, language, setLanguage } = useLanguage();
  const fullNames: Record<Language, string> = {
    en: t.languageSwitcher.english,
    vi: t.languageSwitcher.vietnamese,
  };

  const handleSelect = (value: Language) => {
    setLanguage(value);
  };

  return (
    <div
      role="group"
      aria-label={t.languageSwitcher.label}
      className="inline-flex items-stretch border-[3px] border-ink"
    >
      {OPTIONS.map(({ value, short }) => {
        const isActive = language === value;
        return (
          <button
            key={value}
            type="button"
            lang={value}
            aria-pressed={isActive}
            aria-label={fullNames[value]}
            title={fullNames[value]}
            onClick={() => handleSelect(value)}
            className={cn(
              "min-h-11 min-w-11 cursor-pointer px-2.5 font-display text-base leading-none font-bold uppercase transition-colors",
              isActive ? "bg-ink text-on-ink" : "bg-transparent text-ink hover:bg-signal"
            )}
          >
            {short}
          </button>
        );
      })}
    </div>
  );
};

export default LanguageSwitcher;
