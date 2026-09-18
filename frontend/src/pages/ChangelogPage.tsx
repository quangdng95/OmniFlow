import { type Page } from "../components/Header";
import SectionCard from "../components/SectionCard";
import { useLanguage } from "../i18n/LanguageContext";

interface ChangelogPageProps {
  onNavigate: (page: Page) => void;
}

const ChangelogPage = ({ onNavigate: _onNavigate }: ChangelogPageProps) => {
  const { t } = useLanguage();

  return (
    <div className="w-full select-none flex flex-col gap-4">
      <SectionCard className="p-6 bg-white border border-slate-200/50 shadow-sm rounded-xl flex flex-col gap-2">
        <span className="text-[11px] font-mono font-bold uppercase tracking-wider text-[#0d9585]">
          {t.changelog.eyebrow}
        </span>
        <h3 className="text-lg font-bold text-slate-900 m-0">{t.changelog.heading}</h3>
        <p className="text-sm text-slate-600 leading-relaxed m-0">{t.changelog.intro}</p>
      </SectionCard>

      {t.changelog.releases.map((release) => (
        <SectionCard
          key={release.date}
          className="p-0 bg-white border border-slate-200/50 shadow-sm rounded-xl overflow-hidden flex flex-col gap-0"
        >
          <div className="flex items-baseline gap-3 px-5 py-4 bg-slate-50 border-b border-slate-100">
            <span className="font-mono text-xs font-bold text-[#0d9585] shrink-0 whitespace-nowrap">
              {release.date}
            </span>
            <span className="text-sm font-extrabold text-slate-900">{release.title}</span>
          </div>
          <ul className="flex flex-col px-5 py-2 list-none pl-0">
            {release.items.map((item, i) => (
              <li
                key={i}
                className="text-sm leading-relaxed py-2.5 border-t border-dashed border-slate-100 first:border-t-0 text-slate-700"
              >
                {item}
              </li>
            ))}
          </ul>
        </SectionCard>
      ))}
    </div>
  );
};

export default ChangelogPage;
