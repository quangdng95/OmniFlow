import { type Page } from "../components/Header";
import SectionCard from "../components/SectionCard";
import { useLanguage } from "../i18n/LanguageContext";

interface TermsPageProps {
  onNavigate: (page: Page) => void;
}

const TermsPage = ({ onNavigate: _onNavigate }: TermsPageProps) => {
  const { t } = useLanguage();
  return (
    <div className="w-full">
      <div className="w-full flex flex-col gap-4">
          <SectionCard className="p-5 md:p-6 flex flex-col gap-6 text-ink">
            {/* Header info */}
            <div className="flex flex-col gap-2 border-b-[3px] border-ink pb-4">
              <p className="text-lg font-bold text-ink m-0">{t.terms.heading}</p>
              <div className="flex gap-2 items-baseline text-base text-ink-muted">
                <span>{t.terms.lastUpdatedLabel}</span>
                <span className="font-semibold text-ink">{t.terms.lastUpdatedValue}</span>
              </div>
              <p className="text-base text-ink-muted leading-relaxed mt-2 m-0">{t.terms.intro}</p>
            </div>

            {/* Sections content */}
            <div className="flex flex-col gap-5">
              {t.terms.sections.map((section) => (
                <div key={section.heading} className="flex flex-col gap-2">
                  <h3 className="text-base font-bold text-ink m-0">{section.heading}</h3>
                  <p className="text-base text-ink-muted leading-relaxed m-0">{section.body}</p>
                  
                  {section.list && (
                    <ul className="list-disc pl-5 text-base text-ink-muted flex flex-col gap-1.5 mt-1.5">
                      {section.list.map((item) => (
                        <li key={item} className="pl-1">{item}</li>
                      ))}
                    </ul>
                  )}
                  {section.trailing && (
                    <p className="text-base text-ink-muted leading-relaxed m-0 mt-1">{section.trailing}</p>
                  )}
                </div>
              ))}
            </div>
          </SectionCard>

      </div>
    </div>
  );
};

export default TermsPage;
