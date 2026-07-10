import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { translations, type Language, type Translations } from "./translations";
import { Toaster } from "@/components/ui/sonner";

const STORAGE_KEY = "omniflow-language";

interface LanguageContextValue {
  language: Language;
  setLanguage: (language: Language) => void;
  t: Translations;
}

const LanguageContext = createContext<LanguageContextValue | null>(null);

const readStoredLanguage = (): Language => {
  const stored = localStorage.getItem(STORAGE_KEY);
  return stored === "vi" ? "vi" : "en";
};

export const LanguageProvider = ({ children }: { children: ReactNode }) => {
  const [language, setLanguageState] = useState<Language>(readStoredLanguage);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, language);
  }, [language]);

  const setLanguage = (next: Language) => setLanguageState(next);

  return (
    <LanguageContext.Provider value={{ language, setLanguage, t: translations[language] }}>
      {children}
      <Toaster position="top-center" closeButton />
    </LanguageContext.Provider>
  );
};

export const useLanguage = (): LanguageContextValue => {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error("useLanguage must be used within a LanguageProvider");
  }
  return context;
};
