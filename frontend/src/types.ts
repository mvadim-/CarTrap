export type UserRole = "admin" | "user";

export type User = {
  id: string;
  email: string;
  role: UserRole;
  status: string;
};

export type TokenPair = {
  access_token: string;
  refresh_token: string;
  token_type: string;
};

export type WatchlistItem = {
  id: string;
  lot_number: string;
  url: string;
  title: string;
  thumbnail_url: string | null;
  image_urls: string[];
  status: string;
  raw_status: string;
  current_bid: number | null;
  buy_now_price: number | null;
  currency: string;
  sale_date: string | null;
  last_checked_at: string;
  created_at: string;
};

export type SearchResult = {
  lot_number: string;
  title: string;
  url: string;
  thumbnail_url: string | null;
  location: string | null;
  sale_date: string | null;
  current_bid: number | null;
  currency: string;
  status: string;
};

export type SavedSearchCriteria = {
  make?: string;
  model?: string;
  make_filter?: string;
  model_filter?: string;
  drive_type?: string;
  primary_damage?: string;
  title_type?: string;
  fuel_type?: string;
  lot_condition?: string;
  odometer_range?: string;
  year_from?: number;
  year_to?: number;
  lot_number?: string;
};

export type SavedSearch = {
  id: string;
  label: string;
  criteria: SavedSearchCriteria;
  external_url: string;
  result_count: number | null;
  created_at: string;
};

export type SearchResultsResponse = {
  results: SearchResult[];
  total_results: number;
};

export type SearchCatalogModel = {
  slug: string;
  name: string;
  search_filter: string;
};

export type SearchCatalogMake = {
  slug: string;
  name: string;
  aliases: string[];
  search_filter: string;
  models: SearchCatalogModel[];
};

export type SearchCatalogSummary = {
  make_count: number;
  model_count: number;
  assigned_model_count: number;
  exact_match_count: number;
  fuzzy_match_count: number;
  unassigned_model_count: number;
  year_count: number;
};

export type SearchCatalog = {
  generated_at: string | null;
  updated_at: string | null;
  summary: SearchCatalogSummary;
  years: number[];
  makes: SearchCatalogMake[];
  manual_override_count: number;
};

export type Invite = {
  id: string;
  email: string;
  status: string;
  token: string;
  expires_at: string;
};

export type PushSubscriptionItem = {
  id: string;
  endpoint: string;
  user_agent: string | null;
  created_at: string;
  updated_at: string;
};
