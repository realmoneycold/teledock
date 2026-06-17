"use client";

import { useState, useEffect } from "react";
import {
  Copy,
  CreditCard,
  CheckCircle,
  ArrowLeft,
  Banknote,
  Loader2,
  User,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useTelegram } from "@/context/telegram";
import { useLanguage } from "@/context/language";
import {
  createDepositRequest,
  getDepositStatus,
  type DepositResponse,
} from "@/lib/api";

const DEPOSIT_OPTIONS = [
  { label: "5,000 UZS", baseTiyin: 500_000 },
  { label: "10,000 UZS", baseTiyin: 1_000_000 },
  { label: "20,000 UZS", baseTiyin: 2_000_000 },
  { label: "40,000 UZS", baseTiyin: 4_000_000 },
  { label: "50,000 UZS", baseTiyin: 5_000_000 },
  { label: "100,000 UZS", baseTiyin: 10_000_000 },
  { label: "200,000 UZS", baseTiyin: 20_000_000 },
  { label: "500,000 UZS", baseTiyin: 50_000_000 },
];

interface P2PDepositScreenProps {
  onGoToProfile: () => void;
}

export default function P2PDepositScreen({ onGoToProfile }: P2PDepositScreenProps) {
  const { isDark } = useTelegram();
  const { t } = useLanguage();
  const [deposit, setDeposit] = useState<DepositResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [cardCopied, setCardCopied] = useState(false);
  const [polling, setPolling] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [confirmedAmount, setConfirmedAmount] = useState(0);

  const handleSelect = async (opt: { label: string; baseTiyin: number }) => {
    setBusy(true);
    setError(null);
    setConfirmed(false);
    setPolling(false);
    try {
      const res = await createDepositRequest(opt.baseTiyin);
      setDeposit(res);
      setCopied(false);
      setCardCopied(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create deposit");
    } finally {
      setBusy(false);
    }
  };

  const handleCopy = async () => {
    if (!deposit) return;
    try {
      await navigator.clipboard.writeText(deposit.unique_amount_uzs.toString());
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };

  // Poll for deposit confirmation
  useEffect(() => {
    if (!polling || !deposit) return;

    const interval = setInterval(async () => {
      try {
        const result = await getDepositStatus(deposit.transaction_id);
        if (result.ok && result.status === "completed") {
          setPolling(false);
          setConfirmed(true);
          setConfirmedAmount(result.amount_uzs ?? 0);
        }
      } catch {
        // ignore polling errors
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [polling, deposit]);

  // Success screen
  if (confirmed) {
    const amountUzs = confirmedAmount.toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });

    return (
      <div className="space-y-6 text-center">
        <div
          className={cn(
            "rounded-2xl border p-8",
            isDark
              ? "border-slate-700 bg-slate-800"
              : "border-slate-100 bg-white shadow-sm"
          )}
        >
          <CheckCircle className="mx-auto h-16 w-16 text-emerald-500" />
          <h3
            className={cn(
              "mt-4 text-xl font-bold",
              isDark ? "text-white" : "text-slate-900"
            )}
          >
            {t("deposit_confirmed")}
          </h3>
          <p
            className={cn(
              "mt-2 text-sm",
              isDark ? "text-slate-400" : "text-slate-500"
            )}
          >
            {t("deposit_confirmed_desc")}
          </p>

          <div className="mt-5">
            <p
              className={cn(
                "text-xs font-semibold uppercase tracking-wide",
                isDark ? "text-slate-400" : "text-slate-500"
              )}
            >
              {t("amount_added")}
            </p>
            <p
              className={cn(
                "mt-1 text-3xl font-extrabold",
                isDark ? "text-white" : "text-slate-900"
              )}
            >
              {amountUzs} <span className="text-lg font-semibold">UZS</span>
            </p>
          </div>
        </div>

        <button
          onClick={onGoToProfile}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-brand-500 py-3 text-sm font-bold text-white transition-opacity hover:opacity-90"
        >
          <User className="h-4 w-4" />
          {t("go_to_profile")}
        </button>
      </div>
    );
  }

  if (deposit) {
    const uniqueUzs = deposit.unique_amount_uzs.toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });

    return (
      <div className="space-y-5">
        <button
          onClick={() => {
            setDeposit(null);
            setPolling(false);
          }}
          className={cn(
            "flex items-center gap-2 text-sm font-medium",
            isDark ? "text-slate-300" : "text-slate-600"
          )}
        >
          <ArrowLeft className="h-4 w-4" />
          {t("back")}
        </button>

        <div
          className={cn(
            "rounded-2xl border p-5 text-center",
            isDark
              ? "border-slate-700 bg-slate-800"
              : "border-slate-100 bg-white shadow-sm"
          )}
        >
          <p className={cn("mb-1 text-sm", isDark ? "text-slate-400" : "text-slate-500")}>
            {t("base_amount")}
          </p>
          <p className={cn("mb-4 text-lg font-bold line-through", isDark ? "text-slate-500" : "text-slate-400")}>
            {(deposit.base_tiyin / 100).toLocaleString("en-US", { minimumFractionDigits: 2 })} UZS
          </p>

          <p className={cn("mb-1 text-sm font-medium", isDark ? "text-brand-300" : "text-brand-600")}>
            {t("send_exactly")}
          </p>
          <div className="mb-4 flex items-center justify-center gap-2">
            <span className={cn("text-3xl font-black tracking-tight", isDark ? "text-white" : "text-slate-900")}>
              {uniqueUzs}
            </span>
            <span className={cn("text-lg font-semibold", isDark ? "text-slate-400" : "text-slate-500")}>
              UZS
            </span>
          </div>

          <button
            onClick={handleCopy}
            className={cn(
              "flex w-full items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-bold transition-colors",
              copied
                ? "bg-emerald-500 text-white"
                : isDark
                ? "bg-slate-700 text-white hover:bg-slate-600"
                : "bg-brand-500 text-white hover:bg-brand-600"
            )}
          >
            {copied ? (
              <>
                <CheckCircle className="h-4 w-4" />
                Copied!
              </>
            ) : (
              <>
                <Copy className="h-4 w-4" />
                {t("copy_amount")}
              </>
            )}
          </button>

          <p className={cn("mt-2 text-xs", isDark ? "text-slate-400" : "text-slate-500")}>
            {t("top_up_desc")}
          </p>
        </div>

        <div
          className={cn(
            "rounded-2xl border p-5",
            isDark
              ? "border-slate-700 bg-slate-800"
              : "border-slate-100 bg-white shadow-sm"
          )}
        >
          <div className="mb-4 flex items-center gap-3">
            <div className={cn("flex h-10 w-10 items-center justify-center rounded-xl", isDark ? "bg-slate-700" : "bg-brand-50")}>
              <CreditCard className="h-5 w-5 text-brand-500" />
            </div>
            <div>
              <p className={cn("text-sm font-bold", isDark ? "text-white" : "text-slate-900")}>
                {t("transfer_to_card")}
              </p>
              <p className={cn("text-xs", isDark ? "text-slate-400" : "text-slate-500")}>
                {deposit.card_holder}
              </p>
            </div>
          </div>

          <div
            className={cn(
              "rounded-xl border p-4 text-center font-mono text-lg font-bold tracking-wider",
              isDark
                ? "border-slate-600 bg-slate-900 text-white"
                : "border-slate-200 bg-slate-50 text-slate-900"
            )}
          >
            {deposit.card_number}
          </div>

          <button
            onClick={async () => {
              try {
                await navigator.clipboard.writeText(deposit.card_number);
                setCardCopied(true);
                setTimeout(() => setCardCopied(false), 2000);
              } catch { /* noop */ }
            }}
            className={cn(
              "mt-3 flex w-full items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-bold transition-colors",
              cardCopied
                ? "bg-emerald-500 text-white"
                : isDark
                ? "bg-slate-700 text-white hover:bg-slate-600"
                : "bg-brand-500 text-white hover:bg-brand-600"
            )}
          >
            {cardCopied ? (
              <>
                <CheckCircle className="h-4 w-4" />
                Copied!
              </>
            ) : (
              <>
                <Copy className="h-4 w-4" />
                {t("copy_card")}
              </>
            )}
          </button>
        </div>

        <button
          onClick={() => setPolling(true)}
          disabled={polling}
          className={cn(
            "flex w-full items-center justify-center gap-2 rounded-xl py-3 text-sm font-bold text-white transition-opacity hover:opacity-90 disabled:opacity-60",
            polling ? "bg-emerald-500" : "bg-brand-500"
          )}
        >
          {polling ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              {t("waiting_confirmation")}
            </>
          ) : (
            <>
              <CheckCircle className="h-4 w-4" />
              {t("i_have_paid")}
            </>
          )}
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="mb-2">
        <h3 className={cn("text-lg font-bold", isDark ? "text-white" : "text-slate-900")}>
          {t("top_up_balance")}
        </h3>
        <p className={cn("text-sm", isDark ? "text-slate-400" : "text-slate-500")}>
          {t("top_up_desc")}
        </p>
      </div>

      {error && (
        <div className="rounded-xl bg-rose-50 p-3 text-sm font-medium text-rose-600 dark:bg-rose-900/30 dark:text-rose-400">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
        {DEPOSIT_OPTIONS.map((opt) => (
          <button
            key={opt.baseTiyin}
            onClick={() => handleSelect(opt)}
            disabled={busy}
            className={cn(
              "flex items-center justify-between rounded-xl border px-4 py-3 text-left transition-all active:scale-[0.98] disabled:opacity-60",
              isDark
                ? "border-slate-700 bg-slate-800 text-white hover:bg-slate-700"
                : "border-slate-100 bg-white text-slate-900 shadow-sm hover:border-brand-200 hover:bg-brand-50"
            )}
          >
            <span className="flex items-center gap-3">
              <div className={cn("flex h-9 w-9 items-center justify-center rounded-lg", isDark ? "bg-slate-700" : "bg-brand-50")}>
                <Banknote className="h-5 w-5 text-brand-500" />
              </div>
              <span className="text-base font-bold">{opt.label}</span>
            </span>
            <span className={cn("text-sm font-semibold", isDark ? "text-brand-300" : "text-brand-600")}>
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : "Select →"}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
