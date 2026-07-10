import { type Page } from "../components/Header";
import SectionCard from "../components/SectionCard";
import { useLanguage } from "../i18n/LanguageContext";

interface TermsPageProps {
  onNavigate: (page: Page) => void;
}

const TermsPage = ({ onNavigate: _onNavigate }: TermsPageProps) => {
  const { t } = useLanguage();
  return (
    <div className="w-full select-none">
      <div className="w-full flex flex-col gap-4">
          <SectionCard className="p-6 bg-white border border-slate-200/50 shadow-sm rounded-xl flex flex-col gap-6 text-slate-800">
            {/* Header info */}
            <div className="flex flex-col gap-2 border-b border-neutral-100 pb-4">
              <p className="text-lg font-bold text-slate-900 m-0">{t.terms.heading}</p>
              <div className="flex gap-2 items-baseline text-xs text-slate-500">
                <span>{t.terms.lastUpdatedLabel}</span>
                <span className="font-semibold text-slate-700">{t.terms.lastUpdatedValue}</span>
              </div>
              <p className="text-sm text-slate-600 leading-relaxed mt-2 m-0">{t.terms.intro}</p>
            </div>

            {/* Sections content */}
            <div className="flex flex-col gap-5">
              {t.terms.sections.map((section) => (
                <div key={section.heading} className="flex flex-col gap-2">
                  <h3 className="text-sm font-bold text-slate-900 m-0">{section.heading}</h3>
                  <p className="text-xs text-slate-600 leading-relaxed m-0">{section.body}</p>
                  
                  {section.list && (
                    <ul className="list-disc pl-5 text-xs text-slate-600 flex flex-col gap-1.5 mt-1.5">
                      {section.list.map((item) => (
                        <li key={item} className="pl-1">{item}</li>
                      ))}
                    </ul>
                  )}
                  {section.trailing && (
                    <p className="text-xs text-slate-600 leading-relaxed m-0 mt-1">{section.trailing}</p>
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
