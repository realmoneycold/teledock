export interface UserProfile {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
  photo_url?: string;
}

export interface ProductItem {
  id: string;
  name: string;
  cost_tiyin: number;
  details: Record<string, unknown>;
}

export interface ProductCategory {
  label: string;
  items: ProductItem[];
}

export interface DepositOption {
  label: string;
  base_tiyin: number;
}

export type AppTab = "catalog" | "deposit" | "profile";
