"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  ReactNode,
} from "react";
import type { WebApp as TwaWebApp, WebAppUser } from "@twa-dev/types";

interface TelegramContextValue {
  webApp: TwaWebApp | null;
  user: WebAppUser | null;
  initData: string;
  ready: boolean;
  expand: () => void;
  isDark: boolean;
}

const TelegramContext = createContext<TelegramContextValue>({
  webApp: null,
  user: null,
  initData: "",
  ready: false,
  expand: () => {},
  isDark: false,
});

export function TelegramProvider({ children }: { children: ReactNode }) {
  const [webApp, setWebApp] = useState<TwaWebApp | null>(null);
  const [user, setUser] = useState<WebAppUser | null>(null);
  const [initData, setInitData] = useState("");
  const [ready, setReady] = useState(false);
  const [isDark, setIsDark] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const init = async () => {
      try {
        const { default: TwaSdk } = await import("@twa-dev/sdk");
        const app = TwaSdk;

        if (app && app.ready) {
          app.ready();
          app.expand();

          setWebApp(app);
          setUser(app.initDataUnsafe.user ?? null);
          setInitData(app.initData || "");
          setIsDark(app.colorScheme === "dark");
          setReady(true);

          app.onEvent("themeChanged", () => {
            setIsDark(app.colorScheme === "dark");
          });
        } else {
          // Not running inside Telegram — mock for dev
          setReady(true);
        }
      } catch {
        setReady(true);
      }
    };

    init();
  }, []);

  const expand = () => {
    if (webApp && webApp.expand) {
      webApp.expand();
    }
  };

  return (
    <TelegramContext.Provider value={{ webApp, user, initData, ready, expand, isDark }}>
      {children}
    </TelegramContext.Provider>
  );
}

export function useTelegram() {
  return useContext(TelegramContext);
}
