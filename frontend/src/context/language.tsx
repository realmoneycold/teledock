"use client";

import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react";
import { t, type SupportedLang, DEFAULT_LANG, LANG_NAMES } from "@/lib/i18n";
import { changeLanguage } from "@/lib/api";

interface LanguageContextType {
  lang: SupportedLang;
  setLang: (lang: SupportedLang) => void;
  t: (key: Parameters<typeof t>[0]) => string;
  langNames: typeof LANG_NAMES;
}

const LanguageContext = createContext<LanguageContextType>({
  lang: DEFAULT_LANG,
  setLang: () => {},
  t: (key) => key,
  langNames: LANG_NAMES,
});

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<SupportedLang>(DEFAULT_LANG);

  useEffect(() => {
    // Load from localStorage on mount
    try {
      const stored = localStorage.getItem("teledock_lang") as SupportedLang | null;
      if (stored && ["en", "uz", "ru"].includes(stored)) {
        setLangState(stored);
      }
    } catch {
      // noop
    }
  }, []);

  const setLang = useCallback(async (newLang: SupportedLang) => {
    setLangState(newLang);
    try {
      localStorage.setItem("teledock_lang", newLang);
    } catch {
      // noop
    }
    // Sync to backend
    try {
      await changeLanguage(newLang);
    } catch {
      // backend might fail but frontend lang still works
    }
  }, []);

  const translate = useCallback(
    (key: Parameters<typeof t>[0]) => t(key, lang),
    [lang]
  );

  return (
    <LanguageContext.Provider value={{ lang, setLang, t: translate, langNames: LANG_NAMES }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  return useContext(LanguageContext);
}
