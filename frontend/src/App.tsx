import { lazy, Suspense, useState } from "react";
import type { Page } from "./components/Header";
import HomePage from "./pages/HomePage";
import { LanguageProvider } from "./i18n/LanguageContext";

const SettingsPage = lazy(() => import("./pages/SettingsPage"));
const TermsPage = lazy(() => import("./pages/TermsPage"));

const App = () => {
  const [page, setPage] = useState<Page>("home");

  return (
    <LanguageProvider>
      <div className="omniflow-container">
        {/* Home stays mounted across navigation so an in-progress check/download
            survives a trip to Settings or Terms and back. */}
        <div style={{ display: page === "home" ? "contents" : "none" }}>
          <HomePage onNavigate={setPage} />
        </div>
        {page !== "home" && (
          <Suspense fallback={null}>
            {page === "settings" && <SettingsPage onNavigate={setPage} />}
            {page === "terms" && <TermsPage onNavigate={setPage} />}
          </Suspense>
        )}
      </div>
    </LanguageProvider>
  );
};

export default App;
