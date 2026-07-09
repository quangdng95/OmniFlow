import { lazy, Suspense, useState } from "react";
import Header, { type Page } from "./components/Header";
import Footer from "./components/Footer";
import HomePage from "./pages/HomePage";
import { LanguageProvider } from "./i18n/LanguageContext";

const SettingsPage = lazy(() => import("./pages/SettingsPage"));
const TermsPage = lazy(() => import("./pages/TermsPage"));

const App = () => {
  const [page, setPage] = useState<Page>("home");

  return (
    <LanguageProvider>
      <div className="w-full min-h-screen bg-[#f4f4f0] flex flex-col items-center">
        {/* Full-width Header */}
        <Header active={page} onNavigate={setPage} />

        {/* Content area */}
        <div className="w-full max-w-[680px] flex flex-col gap-4 py-6 px-4 flex-grow">
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

          <Footer />
        </div>
      </div>
    </LanguageProvider>
  );
};

export default App;
