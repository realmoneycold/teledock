"use client";

import Image from "next/image";
import { Wallet, User, Loader2 } from "lucide-react";
import { useTelegram } from "@/context/telegram";
import { useLanguage } from "@/context/language";
import { cn } from "@/lib/utils";

interface DashboardHeaderProps {
  balanceUzs: string;
  loading?: boolean;
}

export default function DashboardHeader({ balanceUzs, loading }: DashboardHeaderProps) {
  const { user, isDark } = useTelegram();
  const { t } = useLanguage();

  return (
    <header
      className={cn(
        "flex items-center gap-4 rounded-2xl p-4 shadow-sm",
        isDark ? "bg-slate-800 text-white" : "bg-white text-slate-900"
      )}
    >
      <div className="relative h-14 w-14 shrink-0 overflow-hidden rounded-full border-2 border-brand-500">
        {user?.photo_url ? (
          <Image
            src={user.photo_url}
            alt={user.first_name}
            fill
            className="object-cover"
            unoptimized
          />
        ) : (
          <div
            className={cn(
              "flex h-full w-full items-center justify-center",
              isDark ? "bg-slate-700" : "bg-brand-50"
            )}
          >
            <User className="h-7 w-7 text-brand-500" />
          </div>
        )}
      </div>

      <div className="flex-1 min-w-0">
        <p className={cn("text-sm font-medium", isDark ? "text-slate-300" : "text-slate-500")}>
          {t("welcome")}
        </p>
        <h2 className="truncate text-lg font-bold leading-tight">
          {user?.first_name ?? "TeleDock User"}
        </h2>
      </div>

      <div
        className={cn(
          "flex flex-col items-end rounded-xl px-3 py-2",
          isDark ? "bg-slate-900" : "bg-brand-50"
        )}
      >
        <span className={cn("text-xs font-medium", isDark ? "text-brand-300" : "text-brand-600")}>
          {t("wallet")}
        </span>
        <span className="flex items-center gap-1 text-sm font-bold text-brand-600">
          {loading ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Wallet className="h-3.5 w-3.5" />
          )}
          {loading ? "..." : `${balanceUzs} UZS`}
        </span>
      </div>
    </header>
  );
}
