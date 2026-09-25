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
      className="inline-flex items-center rounded-full border border-neutral-200 bg-[#f5f5f5] p-0.5"
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
              "rounded-full px-3 py-1 text-xs font-semibold leading-none transition-colors",
              isActive ? "bg-[#171717] text-[#fafafa] shadow-sm" : "text-[#171717] hover:bg-neutral-200"
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
