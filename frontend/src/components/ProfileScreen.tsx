"use client";

import Image from "next/image";
import { User, Wallet, Clock, ArrowUpRight, ArrowDownRight, Globe } from "lucide-react";
import { cn } from "@/lib/utils";
import { useTelegram } from "@/context/telegram";
import { useLanguage } from "@/context/language";
import { type TransactionRecord } from "@/lib/api";

interface ProfileScreenProps {
  balanceUzs: string;
  loading?: boolean;
  transactions: TransactionRecord[];
}

export default function ProfileScreen({ balanceUzs, loading, transactions }: ProfileScreenProps) {
  const { user, isDark } = useTelegram();
  const { t, lang, setLang, langNames } = useLanguage();

  const formatAmount = (amountUzs: number, provider: string) => {
    const isPositive = provider === "p2p" || provider === "humo_cardbot";
    const formatted = amountUzs.toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
    return {
      text: `${isPositive ? "+" : "-"}${formatted} UZS`,
      positive: isPositive,
    };
  };

  const getTxLabel = (tx: TransactionRecord) => {
    const provider = tx.provider.toLowerCase();
    if (provider === "p2p" || provider === "humo_cardbot") return t("deposit_label");
    if (provider === "wallet") return t("purchase_label");
    if (provider === "payme" || provider === "click") return "Payment";
    return tx.provider;
  };

  const langs = [
    { code: "en" as const, flag: "🇺🇸" },
    { code: "uz" as const, flag: "🇺🇿" },
    { code: "ru" as const, flag: "🇷🇺" },
  ];

  return (
    <div className="space-y-5">
      {/* Profile card */}
      <div
        className={cn(
          "flex flex-col items-center rounded-2xl border p-6 text-center",
          isDark
            ? "border-slate-700 bg-slate-800"
            : "border-slate-100 bg-white shadow-sm"
        )}
      >
        <div className="relative mb-3 h-20 w-20 overflow-hidden rounded-full border-2 border-brand-500">
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
              <User className="h-9 w-9 text-brand-500" />
            </div>
          )}
        </div>
        <h2
          className={cn(
            "text-xl font-bold",
            isDark ? "text-white" : "text-slate-900"
          )}
        >
          {user?.first_name ?? "TeleDock User"}
          {user?.last_name ? ` ${user.last_name}` : ""}
        </h2>
        {user?.username && (
          <p
            className={cn(
              "text-sm",
              isDark ? "text-slate-400" : "text-slate-500"
            )}
          >
            @{user.username}
          </p>
        )}

        <div
          className={cn(
            "mt-4 flex items-center gap-2 rounded-xl px-4 py-2",
            isDark ? "bg-slate-900" : "bg-brand-50"
          )}
        >
          <Wallet className="h-4 w-4 text-brand-500" />
          <span
            className={cn(
              "text-sm font-bold",
              isDark ? "text-brand-300" : "text-brand-700"
            )}
          >
            {loading ? "..." : `${balanceUzs} UZS`}
          </span>
        </div>
      </div>

      {/* History */}
      <div>
        <div className="mb-2 flex items-center gap-2">
          <Clock className="h-4 w-4 text-slate-400" />
          <h3
            className={cn(
              "text-sm font-bold uppercase tracking-wide",
              isDark ? "text-slate-300" : "text-slate-500"
            )}
          >
            {t("recent_activity")}
          </h3>
        </div>
        <div className="space-y-2">
          {transactions.length === 0 ? (
            <p className={cn("text-center text-sm py-6", isDark ? "text-slate-500" : "text-slate-400")}>
              {t("no_transactions")}
            </p>
          ) : (
            transactions.map((tx) => {
              const { text, positive } = formatAmount(tx.amount_uzs, tx.provider);
              return (
                <div
                  key={tx.id}
                  className={cn(
                    "flex items-center justify-between rounded-xl border px-4 py-3",
                    isDark
                      ? "border-slate-700 bg-slate-800"
                      : "border-slate-100 bg-white shadow-sm"
                  )}
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={cn(
                        "flex h-8 w-8 items-center justify-center rounded-lg",
                        isDark ? "bg-slate-700" : "bg-slate-50"
                      )}
                    >
                      {positive ? (
                        <ArrowUpRight className="h-4 w-4 text-emerald-500" />
                      ) : (
                        <ArrowDownRight className="h-4 w-4 text-rose-500" />
                      )}
                    </div>
                    <div>
                      <span
                        className={cn(
                          "text-sm font-semibold",
                          isDark ? "text-slate-200" : "text-slate-700"
                        )}
                      >
                        {getTxLabel(tx)}
                      </span>
                      <p className={cn("text-xs", isDark ? "text-slate-500" : "text-slate-400")}>
                        {tx.status}
                      </p>
                    </div>
                  </div>
                  <span
                    className={cn(
                      "text-sm font-bold",
                      positive
                        ? "text-emerald-500"
                        : isDark
                        ? "text-rose-400"
                        : "text-rose-500"
                    )}
                  >
                    {text}
                  </span>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Language Selector */}
      <div
        className={cn(
          "rounded-2xl border p-5",
          isDark
            ? "border-slate-700 bg-slate-800"
            : "border-slate-100 bg-white shadow-sm"
        )}
      >
        <div className="mb-3 flex items-center gap-2">
          <Globe className="h-4 w-4 text-slate-400" />
          <h3
            className={cn(
              "text-sm font-bold uppercase tracking-wide",
              isDark ? "text-slate-300" : "text-slate-500"
            )}
          >
            {t("language")}
          </h3>
        </div>
        <div className="grid grid-cols-3 gap-2">
          {langs.map((l) => (
            <button
              key={l.code}
              onClick={() => setLang(l.code)}
              className={cn(
                "flex items-center justify-center gap-1.5 rounded-lg border px-3 py-2 text-sm font-bold transition-all",
                lang === l.code
                  ? isDark
                    ? "border-brand-500 bg-brand-500/20 text-brand-300"
                    : "border-brand-500 bg-brand-50 text-brand-700"
                  : isDark
                  ? "border-slate-600 bg-slate-700 text-slate-300"
                  : "border-slate-200 bg-white text-slate-600"
              )}
            >
              <span>{l.flag}</span>
              <span>{langNames[l.code]}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
