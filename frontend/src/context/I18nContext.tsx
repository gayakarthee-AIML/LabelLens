import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { TRANSLATIONS, type SupportedLanguage, type TranslationKey } from "@/i18n/locales";

interface I18nContextValue {
  language: SupportedLanguage;
  setLanguage: (lang: SupportedLanguage) => void;
  t: (key: TranslationKey) => string;
}

const I18nContext = createContext<I18nContextValue | null>(null);
const STORAGE_KEY = "labellens.language";

export function I18nProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<SupportedLanguage>(
    () => (localStorage.getItem(STORAGE_KEY) as SupportedLanguage) || "en"
  );

  const setLanguage = (lang: SupportedLanguage) => {
    localStorage.setItem(STORAGE_KEY, lang);
    setLanguageState(lang);
  };

  const value = useMemo<I18nContextValue>(
    () => ({
      language,
      setLanguage,
      t: (key) => TRANSLATIONS[language][key] ?? TRANSLATIONS.en[key] ?? key
    }),
    [language]
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useTranslation() {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useTranslation must be used inside I18nProvider");
  return ctx;
}
