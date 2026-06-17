"use client";

import { Store, Wallet, UserCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { useTelegram } from "@/context/telegram";
import { useLanguage } from "@/context/language";

export type TabKey = "catalog" | "deposit" | "profile";

interface BottomNavProps {
  active: TabKey;
  onChange: (tab: TabKey) => void;
}

export default function BottomNav({ active, onChange }: BottomNavProps) {
  const { isDark } = useTelegram();
  const { t } = useLanguage();

  const tabs: { key: TabKey; label: string; icon: React.ReactNode }[] = [
    { key: "catalog", label: t("catalog"), icon: <Store className="h-5 w-5" /> },
    { key: "deposit", label: t("deposit"), icon: <Wallet className="h-5 w-5" /> },
    {
      key: "profile",
      label: t("profile"),
      icon: <UserCircle className="h-5 w-5" />,
    },
  ];

  return (
    <nav
      className={cn(
        "fixed bottom-0 left-0 right-0 z-50 border-t backdrop-blur-md",
        isDark
          ? "border-slate-700 bg-slate-900/90"
          : "border-slate-100 bg-white/90"
      )}
    >
      <div className="mx-auto flex max-w-md items-center justify-around px-2 pb-[env(safe-area-inset-bottom)] pt-2">
        {tabs.map((tab) => {
          const isActive = active === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => onChange(tab.key)}
              className={cn(
                "flex flex-1 flex-col items-center gap-0.5 rounded-lg py-2 transition-colors",
                isActive
                  ? isDark
                    ? "text-brand-400"
                    : "text-brand-600"
                  : isDark
                  ? "text-slate-500"
                  : "text-slate-400"
              )}
            >
              <div
                className={cn(
                  "flex h-8 w-8 items-center justify-center rounded-full transition-colors",
                  isActive
                    ? isDark
                      ? "bg-brand-500/20"
                      : "bg-brand-50"
                    : "bg-transparent"
                )}
              >
                {tab.icon}
              </div>
              <span className="text-[11px] font-semibold">{tab.label}</span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
