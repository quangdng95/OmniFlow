import { lazy, Suspense, useState } from "react";
import Header, { type Page } from "./components/Header";
import PageTitle from "./components/PageTitle";
import Footer from "./components/Footer";
import HomePage from "./pages/HomePage";
import { LanguageProvider } from "./i18n/LanguageContext";

const HistoryPage = lazy(() => import("./pages/HistoryPage"));
const SettingsPage = lazy(() => import("./pages/SettingsPage"));
const TermsPage = lazy(() => import("./pages/TermsPage"));
const ShortcutSetupPage = lazy(() => import("./pages/ShortcutSetupPage"));
const ChangelogPage = lazy(() => import("./pages/ChangelogPage"));

const App = () => {
  const [page, setPage] = useState<Page>("home");
  // A link picked from History: Home fills it in (which re-checks it) and
  // clears this again, so going back to Home later doesn't re-apply it.
  const [pendingUrl, setPendingUrl] = useState<string | null>(null);

  const handleOpenHistoryUrl = (url: string) => {
    setPendingUrl(url);
    setPage("home");
  };

  return (
    <LanguageProvider>
      <div className="w-full min-h-screen bg-[#f4f4f0] flex flex-col items-center">
        {/* Full-width Header */}
        <Header active={page} onNavigate={setPage} />

        {/* Content area */}
        <div className="w-full max-w-[680px] flex flex-col gap-4 py-4 px-4 flex-grow">
          {/* Home stays mounted across navigation so an in-progress check/download
              survives a trip to Settings or Terms and back. */}
          <div style={{ display: page === "home" ? "contents" : "none" }}>
            <HomePage onNavigate={setPage} pendingUrl={pendingUrl} onPendingUrlConsumed={() => setPendingUrl(null)} />
          </div>
          {page !== "home" && <PageTitle page={page} />}
          {page !== "home" && (
            <Suspense fallback={null}>
              {page === "history" && <HistoryPage onNavigate={setPage} onOpenUrl={handleOpenHistoryUrl} />}
              {page === "settings" && <SettingsPage onNavigate={setPage} />}
              {page === "terms" && <TermsPage onNavigate={setPage} />}
              {page === "shortcut" && <ShortcutSetupPage onNavigate={setPage} />}
              {page === "changelog" && <ChangelogPage onNavigate={setPage} />}
            </Suspense>
          )}

          <Footer />
        </div>
      </div>
    </LanguageProvider>
  );
};

export default App;
