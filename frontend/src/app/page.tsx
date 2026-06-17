"use client";

import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { useTelegram } from "@/context/telegram";
import { useLanguage } from "@/context/language";
import DashboardHeader from "@/components/DashboardHeader";
import ProductCatalog from "@/components/ProductCatalog";
import P2PDepositScreen from "@/components/P2PDepositScreen";
import ProfileScreen from "@/components/ProfileScreen";
import BottomNav, { type TabKey } from "@/components/BottomNav";
import { fetchUserProfile, fetchTransactions, type UserProfile, type TransactionRecord } from "@/lib/api";

export default function Home() {
  const { isDark, ready } = useTelegram();
  const { setLang } = useLanguage();
  const [tab, setTab] = useState<TabKey>("catalog");
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [profileLoading, setProfileLoading] = useState(true);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [transactions, setTransactions] = useState<TransactionRecord[]>([]);

  async function loadProfile() {
    setProfileLoading(true);
    setProfileError(null);

    // Load profile independently — never let transactions failure break profile
    try {
      const data = await fetchUserProfile();
      setProfile(data);
      // Set language from profile if returned
      if (data.language && ["en", "uz", "ru"].includes(data.language)) {
        setLang(data.language as "en" | "uz" | "ru");
      }
    } catch (err) {
      setProfileError(err instanceof Error ? err.message : "Failed to load profile");
    } finally {
      setProfileLoading(false);
    }

    // Load transactions separately — silent fail
    try {
      const txs = await fetchTransactions(10);
      setTransactions(txs);
    } catch {
      setTransactions([]);
    }
  }

  useEffect(() => {
    if (ready) loadProfile();
  }, [ready]);

  const balanceUzs = profile
    ? profile.wallet_balance_uzs.toLocaleString("en-US", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })
    : "0.00";

  return (
    <main
      className={cn(
        "flex min-h-screen flex-col",
        isDark ? "bg-slate-900 text-white" : "bg-gray-50 text-slate-900"
      )}
    >
      <div className={cn(
        "mx-auto w-full flex-1 px-4 pt-4 pb-24",
        "max-w-md md:max-w-3xl lg:max-w-5xl xl:max-w-6xl"
      )}>
        <DashboardHeader balanceUzs={balanceUzs} loading={profileLoading} />

        {profileError && (
          <div className="mt-3 rounded-xl bg-rose-50 p-3 text-sm font-medium text-rose-600 dark:bg-rose-900/30 dark:text-rose-400">
            {profileError}{" "}
            <button onClick={loadProfile} className="underline">
              Retry
            </button>
          </div>
        )}

        <div className="mt-5">
          {tab === "catalog" && (
            <ProductCatalog onOrderPlaced={loadProfile} balance={profile?.wallet_balance ?? 0} />
          )}
          {tab === "deposit" && <P2PDepositScreen onGoToProfile={() => { setTab("profile"); loadProfile(); }} />}
          {tab === "profile" && (
            <ProfileScreen balanceUzs={balanceUzs} loading={profileLoading} transactions={transactions} />
          )}
        </div>
      </div>

      <BottomNav active={tab} onChange={setTab} />
    </main>
  );
}
