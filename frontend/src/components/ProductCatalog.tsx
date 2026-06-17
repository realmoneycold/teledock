"use client";

import { useEffect, useState } from "react";
import { Star, Crown, ShoppingCart, Loader2, Copy, CheckCircle, AlertTriangle, ArrowLeft, Wallet, CreditCard, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useTelegram } from "@/context/telegram";
import { useLanguage } from "@/context/language";
import { fetchProducts, createOrder, submitOrder, fetchUserProfile, type Product, type Order } from "@/lib/api";

interface ProductCatalogProps {
  onOrderPlaced: () => void;
  balance: number;
}

export default function ProductCatalog({ onOrderPlaced, balance: initialBalance }: ProductCatalogProps) {
  const { isDark } = useTelegram();
  const { t } = useLanguage();
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [activeOrder, setActiveOrder] = useState<Order | null>(null);
  const [balance, setBalance] = useState(initialBalance);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [walletBusy, setWalletBusy] = useState(false);

  useEffect(() => {
    setBalance(initialBalance);
  }, [initialBalance]);

  useEffect(() => {
    setLoading(true);
    fetchProducts()
      .then((productsData) => {
        setProducts(productsData);
        setLoading(false);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to load products");
        setLoading(false);
      });
  }, []);

  const handleBuyClick = (product: Product) => {
    setError(null);
    setSelectedProduct(product);
    setShowPaymentModal(true);
  };

  const handleWalletPay = async () => {
    if (!selectedProduct) return;
    setWalletBusy(true);
    setError(null);
    try {
      const result = await submitOrder(selectedProduct.id);
      if (!result.ok) {
        if (result.error === "insufficient_funds") {
          const need = result.cost ? (result.cost / 100).toLocaleString("en-US") : "?";
          const have = result.balance ? (result.balance / 100).toLocaleString("en-US") : "?";
          setError(`Insufficient balance. You need ${need} UZS but have ${have} UZS.`);
        } else {
          setError(result.error || "Wallet payment failed");
        }
        setShowPaymentModal(false);
        return;
      }
      setBalance(result.new_balance ?? 0);
      setShowPaymentModal(false);
      setActiveOrder({
        id: result.order_id ?? "",
        user_id: 0,
        product_id: selectedProduct.id,
        amount_uzs: result.cost ?? 0,
        exact_amount: null,
        payment_code: "",
        status: "paid",
        created_at: new Date().toISOString(),
      });
      onOrderPlaced();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Wallet payment failed");
      setShowPaymentModal(false);
    } finally {
      setWalletBusy(false);
    }
  };

  const handleP2POrder = async () => {
    if (!selectedProduct) return;
    setBusyId(selectedProduct.id);
    setError(null);
    setShowPaymentModal(false);
    try {
      const order = await createOrder(selectedProduct.id);
      setActiveOrder(order);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Order failed");
    } finally {
      setBusyId(null);
    }
  };

  const handleDone = () => {
    setActiveOrder(null);
    onOrderPlaced();
  };

  if (activeOrder) {
    return <PaymentInstructions order={activeOrder} onDone={handleDone} />;
  }

  if (showPaymentModal && selectedProduct) {
    const price = selectedProduct.price_uzs;
    const hasBalance = balance >= price;
    const priceUzs = (price / 100).toLocaleString("en-US");
    const balanceUzs = (balance / 100).toLocaleString("en-US");
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className={cn("text-lg font-bold", isDark ? "text-white" : "text-slate-900")}>
            Checkout
          </h3>
          <button
            onClick={() => setShowPaymentModal(false)}
            className={cn("rounded-lg p-1", isDark ? "text-slate-400 hover:text-white" : "text-slate-500 hover:text-slate-900")}
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className={cn("rounded-2xl border p-4", isDark ? "border-slate-700 bg-slate-800" : "border-slate-100 bg-white shadow-sm")}>
          <p className={cn("text-sm font-bold", isDark ? "text-white" : "text-slate-900")}>{selectedProduct.name}</p>
          <p className="text-lg font-extrabold text-brand-600">{priceUzs} UZS</p>
        </div>

        <div className="space-y-2">
          {hasBalance && (
            <button
              onClick={handleWalletPay}
              disabled={walletBusy}
              className={cn(
                "flex w-full items-center gap-3 rounded-xl border p-4 transition-all active:scale-[0.98]",
                isDark ? "border-slate-700 bg-slate-800 hover:bg-slate-700" : "border-slate-100 bg-white shadow-sm hover:bg-gray-50"
              )}
            >
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-emerald-600">
                <Wallet className="h-5 w-5" />
              </div>
              <div className="text-left">
                <p className={cn("text-sm font-bold", isDark ? "text-white" : "text-slate-900")}>
                  Pay with Wallet
                </p>
                <p className={cn("text-xs", isDark ? "text-slate-400" : "text-slate-500")}>
                  Balance: {balanceUzs} UZS — instant delivery
                </p>
              </div>
              {walletBusy && <Loader2 className="ml-auto h-5 w-5 animate-spin text-slate-400" />}
            </button>
          )}

          <button
            onClick={handleP2POrder}
            disabled={busyId === selectedProduct.id}
            className={cn(
              "flex w-full items-center gap-3 rounded-xl border p-4 transition-all active:scale-[0.98]",
              isDark ? "border-slate-700 bg-slate-800 hover:bg-slate-700" : "border-slate-100 bg-white shadow-sm hover:bg-gray-50"
            )}
          >
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-blue-100 text-blue-600">
              <CreditCard className="h-5 w-5" />
            </div>
            <div className="text-left">
              <p className={cn("text-sm font-bold", isDark ? "text-white" : "text-slate-900")}>
                Pay with HUMO / Uzcard
              </p>
              <p className={cn("text-xs", isDark ? "text-slate-400" : "text-slate-500")}>
                Card transfer — automatic detection
              </p>
            </div>
            {busyId === selectedProduct.id && <Loader2 className="ml-auto h-5 w-5 animate-spin text-slate-400" />}
          </button>
        </div>

        {!hasBalance && (
          <p className={cn("text-center text-xs", isDark ? "text-slate-400" : "text-slate-500")}>
            Wallet balance too low ({balanceUzs} UZS). Top up first or pay by card.
          </p>
        )}
      </div>
    );
  }

  const stars = products.filter((p) => p.type === "stars");
  const premium = products.filter((p) => p.type === "premium");

  return (
    <div className="space-y-6">
      {error && (
        <div className="rounded-xl bg-rose-50 p-3 text-sm font-medium text-rose-600 dark:bg-rose-900/30 dark:text-rose-400">
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
        </div>
      ) : (
        <>
          {stars.length > 0 && (
            <section>
              <div className="mb-3 flex items-center gap-2">
                <Star className="h-5 w-5 fill-amber-400 text-amber-400" />
                <h3 className={cn("text-lg font-bold", isDark ? "text-white" : "text-slate-900")}>
                  {t("telegram_stars")}
                </h3>
              </div>
              <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
                {stars.map((item) => (
                  <ProductCard
                    key={item.id}
                    item={item}
                    icon={<Star className="h-5 w-5 fill-amber-400 text-amber-400" />}
                    accent="amber"
                    onBuy={handleBuyClick}
                    busy={busyId === item.id}
                  />
                ))}
              </div>
            </section>
          )}

          {premium.length > 0 && (
            <section>
              <div className="mb-3 flex items-center gap-2">
                <Crown className="h-5 w-5 fill-purple-500 text-purple-500" />
                <h3 className={cn("text-lg font-bold", isDark ? "text-white" : "text-slate-900")}>
                  {t("telegram_premium")}
                </h3>
              </div>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
                {premium.map((item) => (
                  <ProductCard
                    key={item.id}
                    item={item}
                    icon={<Crown className="h-5 w-5 fill-purple-500 text-purple-500" />}
                    accent="purple"
                    onBuy={handleBuyClick}
                    busy={busyId === item.id}
                    wide
                  />
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}

function ProductCard({
  item,
  icon,
  accent,
  onBuy,
  busy,
  wide,
}: {
  item: Product;
  icon: React.ReactNode;
  accent: "amber" | "purple";
  onBuy: (product: Product) => void;
  busy: boolean;
  wide?: boolean;
}) {
  const { isDark } = useTelegram();
  const price = (item.price_uzs / 100).toLocaleString("en-US");

  const accentBg =
    accent === "amber"
      ? isDark
        ? "bg-amber-900/30"
        : "bg-amber-50"
      : isDark
        ? "bg-purple-900/30"
        : "bg-purple-50";
  const accentText = accent === "amber" ? "text-amber-600" : "text-purple-600";
  const accentBtn = accent === "amber" ? "bg-amber-500" : "bg-purple-500";

  return (
    <div
      className={cn(
        "flex flex-col rounded-2xl border p-4 transition-all active:scale-[0.98]",
        isDark ? "border-slate-700 bg-slate-800" : "border-slate-100 bg-white shadow-sm",
        wide && "flex-row items-center gap-4"
      )}
    >
      <div className={cn("flex items-center gap-3", wide && "flex-1")}>
        <div className={cn("flex h-10 w-10 items-center justify-center rounded-xl", accentBg)}>
          {icon}
        </div>
        <div>
          <p className={cn("text-sm font-bold", isDark ? "text-white" : "text-slate-900")}>{item.name}</p>
          <p className={cn("text-xs font-semibold", accentText)}>{price} UZS</p>
        </div>
      </div>
      {!wide && <div className="flex-1" />}
      <button
        onClick={() => onBuy(item)}
        disabled={busy}
        className={cn(
          "mt-3 flex items-center justify-center gap-1.5 rounded-xl px-3 py-2 text-sm font-bold text-white transition-opacity hover:opacity-90 disabled:opacity-60",
          accentBtn,
          wide && "mt-0 shrink-0"
        )}
      >
        {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ShoppingCart className="h-3.5 w-3.5" />}
        {busy ? "..." : "Buy Now"}
      </button>
    </div>
  );
}

function PaymentInstructions({ order, onDone }: { order: Order; onDone: () => void }) {
  const { isDark } = useTelegram();
  const [copied, setCopied] = useState(false);
  const amount = order.exact_amount
    ? order.exact_amount.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : order.amount_uzs
    ? (order.amount_uzs / 100).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : "—";
  const cardNumber = order.card_number || "";
  const cardHolder = order.card_holder || "";

  const copyAmount = async () => {
    try {
      await navigator.clipboard.writeText(amount);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // noop
    }
  };

  return (
    <div className="space-y-5">
      <button
        onClick={onDone}
        className={cn(
          "flex items-center gap-2 text-sm font-medium",
          isDark ? "text-slate-400" : "text-slate-500"
        )}
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Catalog
      </button>

      <div
        className={cn(
          "rounded-2xl border p-5 text-center",
          isDark ? "border-slate-700 bg-slate-800" : "border-slate-100 bg-white shadow-sm"
        )}
      >
        <CheckCircle className="mx-auto h-10 w-10 text-emerald-500" />
        <h3 className={cn("mt-3 text-lg font-bold", isDark ? "text-white" : "text-slate-900")}>
          Order Created!
        </h3>
        <p className={cn("mt-1 text-sm", isDark ? "text-slate-400" : "text-slate-500")}>
          Complete the transfer to receive your product.
        </p>
      </div>

      <div
        className={cn(
          "rounded-2xl border p-5",
          isDark ? "border-slate-700 bg-slate-800" : "border-slate-100 bg-white shadow-sm"
        )}
      >
        <div className="space-y-4">
          <div>
            <p className={cn("text-xs font-semibold uppercase tracking-wide", isDark ? "text-slate-400" : "text-slate-500")}>
              Total Amount
            </p>
            <p className={cn("text-2xl font-extrabold", isDark ? "text-white" : "text-slate-900")}>
              {amount} <span className="text-sm font-semibold">UZS</span>
            </p>
          </div>

          <div>
            <p className={cn("text-xs font-semibold uppercase tracking-wide", isDark ? "text-slate-400" : "text-slate-500")}>
              Transfer to card
            </p>
            <p className={cn("text-lg font-mono font-bold", isDark ? "text-white" : "text-slate-900")}>
              {cardNumber}
            </p>
            {cardHolder && (
              <p className={cn("text-sm font-medium", isDark ? "text-slate-300" : "text-slate-600")}>
                {cardHolder}
              </p>
            )}
          </div>

          <div className="rounded-xl bg-amber-50 p-4 dark:bg-amber-900/20">
            <p className="text-xs font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-300">
              Send exactly this amount
            </p>
            <div className="mt-2 flex items-center justify-between gap-3">
              <span className="text-2xl font-extrabold text-amber-800 dark:text-amber-200">
                {amount} <span className="text-sm font-semibold">UZS</span>
              </span>
              <button
                onClick={copyAmount}
                className="flex items-center gap-1.5 rounded-lg bg-amber-500 px-3 py-2 text-sm font-bold text-white transition-opacity hover:opacity-90"
              >
                {copied ? <CheckCircle className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                {copied ? "Copied" : "Copy"}
              </button>
            </div>
          </div>

          <div className="flex items-start gap-2 rounded-lg bg-rose-50 p-3 text-sm text-rose-700 dark:bg-rose-900/20 dark:text-rose-300">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <p className="font-medium">
              Transfer exactly this amount — the unique fraction helps us identify your payment instantly.
            </p>
          </div>
        </div>
      </div>

      <button
        onClick={onDone}
        className="w-full rounded-xl bg-emerald-500 py-3 text-sm font-bold text-white transition-opacity hover:opacity-90"
      >
        Done, I have paid
      </button>
    </div>
  );
}
