const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

function getInitData(): string {
  if (typeof window === "undefined") return "";
  const tg = (window as any).Telegram?.WebApp;
  return tg?.initData || "";
}

async function api<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const initData = getInitData();
  const url = `${API_BASE}${endpoint}`;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (initData) {
    headers["Authorization"] = `tma ${initData}`;
  }

  const res = await fetch(url, {
    ...options,
    headers,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "Unknown error");
    throw new Error(`API ${res.status}: ${text}`);
  }

  return res.json() as Promise<T>;
}

// ---------------------------------------------------------
// User
// ---------------------------------------------------------

export interface UserProfile {
  id: number;
  username: string | null;
  first_name: string;
  wallet_balance: number;
  wallet_balance_uzs: number;
  language: string;
  created_at: string | null;
}

export function fetchUserProfile(): Promise<UserProfile> {
  return api<UserProfile>("/users/me");
}

// ---------------------------------------------------------
// Transactions
// ---------------------------------------------------------

export interface TransactionRecord {
  id: string;
  amount: number;
  amount_uzs: number;
  status: string;
  provider: string;
  created_at: string | null;
}

export function fetchTransactions(limit = 10): Promise<TransactionRecord[]> {
  return api<TransactionRecord[]>(`/users/transactions?limit=${limit}`);
}

// ---------------------------------------------------------
// Deposits
// ---------------------------------------------------------

export interface DepositResponse {
  ok: boolean;
  transaction_id: string;
  base_tiyin: number;
  unique_amount_tiyin: number;
  unique_amount_uzs: number;
  card_number: string;
  masked_card: string;
  card_holder: string;
}

export function createDepositRequest(
  baseTiyin: number
): Promise<DepositResponse> {
  return api<DepositResponse>("/users/deposits", {
    method: "POST",
    body: JSON.stringify({ base_tiyin: baseTiyin }),
  });
}

export interface DepositStatusResponse {
  ok: boolean;
  status?: string;
  amount_tiyin?: number;
  amount_uzs?: number;
  error?: string;
}

export function getDepositStatus(
  txId: string
): Promise<DepositStatusResponse> {
  return api<DepositStatusResponse>(`/users/deposits/${txId}/status`);
}

export function changeLanguage(language: string): Promise<{ ok: boolean; language: string }> {
  return api<{ ok: boolean; language: string }>("/users/language", {
    method: "POST",
    body: JSON.stringify({ language }),
  });
}

// ---------------------------------------------------------
// Products
// ---------------------------------------------------------

export interface Product {
  id: string;
  name: string;
  type: "stars" | "premium";
  price_uzs: number;
  description: string | null;
  is_active: boolean;
}

export function fetchProducts(): Promise<Product[]> {
  return api<Product[]>("/products");
}

// ---------------------------------------------------------
// Orders (Phase 2 P2P)
// ---------------------------------------------------------

export interface OrderResponse {
  ok: boolean;
  order_id?: string;
  product_type?: string;
  cost?: number;
  cost_uzs?: number;
  new_balance?: number;
  new_balance_uzs?: number;
  status?: string;
  error?: string;
  balance?: number;
}

export interface Order {
  id: string;
  user_id: number;
  product_id: string | null;
  amount_uzs: number | null;
  exact_amount: number | null;
  payment_code: string | null;
  status: string;
  created_at: string | null;
  card_number?: string;
  card_holder?: string;
}

export function createOrder(productId: string): Promise<Order> {
  return api<Order>("/orders/create", {
    method: "POST",
    body: JSON.stringify({ product_id: productId }),
  });
}

export function fetchMyOrders(): Promise<Order[]> {
  return api<Order[]>("/orders/me");
}

export function submitOrder(productId: string): Promise<OrderResponse> {
  return api<OrderResponse>("/users/orders", {
    method: "POST",
    body: JSON.stringify({ product_id: productId }),
  });
}
