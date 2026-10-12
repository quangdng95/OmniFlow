import { type Page } from "../components/Header";
import SectionCard from "../components/SectionCard";
import { useLanguage } from "../i18n/LanguageContext";

interface ChangelogPageProps {
  onNavigate: (page: Page) => void;
}

const ChangelogPage = ({ onNavigate: _onNavigate }: ChangelogPageProps) => {
  const { t } = useLanguage();

  return (
    <div className="w-full flex flex-col gap-4">
      <SectionCard className="p-5 md:p-6 flex flex-col gap-2">
        <span className="text-base font-mono font-bold uppercase tracking-wider text-brand">
          {t.changelog.eyebrow}
        </span>
        <h3 className="text-lg font-bold text-ink m-0">{t.changelog.heading}</h3>
        <p className="text-base text-ink-muted leading-relaxed m-0">{t.changelog.intro}</p>
      </SectionCard>

      {t.changelog.releases.map((release) => (
        <SectionCard
          key={`${release.date}|${release.title}`}
          className="p-0 bg-white border border-ink  rounded-none overflow-hidden flex flex-col gap-0"
        >
          <div className="flex items-baseline gap-3 px-5 py-4 bg-muted border-b border-ink">
            <span className="font-mono text-base font-bold text-brand shrink-0 whitespace-nowrap">
              {release.date}
            </span>
            <span className="text-base font-extrabold text-ink">{release.title}</span>
          </div>
          <ul className="flex flex-col px-5 py-2 list-none pl-0">
            {release.items.map((item, i) => (
              <li
                key={i}
                className="text-base leading-relaxed py-2.5 border-t border-dashed border-ink first:border-t-0 text-ink"
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
