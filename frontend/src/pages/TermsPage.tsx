import Header, { type Page } from "../components/Header";
import Footer from "../components/Footer";
import SectionCard from "../components/SectionCard";
import { useLanguage } from "../i18n/LanguageContext";

interface TermsPageProps {
  onNavigate: (page: Page) => void;
}

const TermsPage = ({ onNavigate }: TermsPageProps) => {
  const { t } = useLanguage();
  return (
    <>
      <Header active="terms" onNavigate={onNavigate} />
      <div className="omniflow-content">
        <div className="omniflow-content-inner">
          <SectionCard>
            <p style={{ fontSize: 20, fontWeight: 600, margin: 0 }}>{t.terms.heading}</p>
            <div>
              <div style={{ display: "flex", gap: 4, alignItems: "baseline" }}>
                <span style={{ fontSize: 14 }}>{t.terms.lastUpdatedLabel}</span>
                <span style={{ fontSize: 16, fontWeight: 600 }}>{t.terms.lastUpdatedValue}</span>
              </div>
              <p style={{ fontSize: 14, margin: "8px 0 0" }}>{t.terms.intro}</p>
            </div>
            {t.terms.sections.map((section) => (
              <div key={section.heading}>
                <p style={{ fontSize: 16, fontWeight: 600, margin: 0 }}>{section.heading}</p>
                <p style={{ fontSize: 14, margin: "8px 0 0" }}>{section.body}</p>
                {section.list && (
                  <ul style={{ fontSize: 14, margin: "8px 0 0" }}>
                    {section.list.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                )}
                {section.trailing && <p style={{ fontSize: 14, margin: "8px 0 0" }}>{section.trailing}</p>}
              </div>
            ))}
          </SectionCard>
          <Footer />
        </div>
      </div>
    </>
  );
};

export default TermsPage;
