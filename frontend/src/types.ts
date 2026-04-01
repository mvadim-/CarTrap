export type UserRole = "admin" | "user";
export type AuctionProvider = "copart" | "iaai";

export type FreshnessStatus = "live" | "cached" | "degraded" | "outdated" | "unknown";

export type FreshnessEnvelope = {
  status: FreshnessStatus;
  last_synced_at: string | null;
  stale_after: string | null;
  degraded_reason: string | null;
  retryable: boolean;
};

export type RefreshStatus = "idle" | "repair_pending" | "retryable_failure" | "failed";

export type RefreshState = {
  status: RefreshStatus;
  last_attempted_at: string | null;
  last_succeeded_at: string | null;
  next_retry_at: string | null;
  error_message: string | null;
  retryable: boolean;
  priority_class: string | null;
  last_outcome: string | null;
  metrics: Record<string, number>;
};

export type ProviderConnectionStatus = "connected" | "expiring" | "reconnect_required" | "disconnected" | "error";

export type ProviderConnectionDiagnosticStatus = "ready" | "connection_missing" | "reconnect_required";

export type ProviderConnectionDiagnostic = {
  provider: AuctionProvider;
  status: ProviderConnectionDiagnosticStatus | string;
  message: string;
  connection_id: string | null;
  reconnect_required: boolean;
};

export type ProviderConnection = {
  id: string;
  provider: AuctionProvider;
  provider_label?: string | null;
  status: ProviderConnectionStatus;
  account_label: string | null;
  connected_at: string | null;
  disconnected_at: string | null;
  last_verified_at: string | null;
  last_used_at: string | null;
  expires_at: string | null;
  reconnect_required: boolean;
  usable: boolean;
  bundle_version: number;
  bundle:
    | {
        key_version: string;
        captured_at: string | null;
        expires_at: string | null;
      }
    | null;
  last_error:
    | {
        code: string;
        message: string;
        retryable: boolean;
        occurred_at: string | null;
      }
    | null;
  created_at: string;
  updated_at: string;
};

export type ReliabilitySummary = {
  total: number;
  attention: number;
  retryable_failures: number;
  repair_pending: number;
  failed: number;
  outdated: number;
  degraded: number;
  cached: number;
};

export type ReliabilityDiagnostics = {
  saved_searches: ReliabilitySummary;
  watchlist: ReliabilitySummary;
  total_attention: number;
};

export type User = {
  id: string;
  email: string;
  role: UserRole;
  status: string;
};

export type AdminOverview = {
  generated_at: string;
  users: {
    total: number;
    admins: number;
    regular_users: number;
    active_last_24h: number;
    active_last_7d: number;
    blocked: number;
    disabled: number;
  };
  invites: {
    pending: number;
    accepted: number;
    revoked: number;
    expired: number;
  };
  providers: {
    total_connections: number;
    connected: number;
    expiring: number;
    reconnect_required: number;
    disconnected: number;
    error: number;
    connected_users: number;
    reconnect_required_users: number;
    disconnected_users: number;
  };
  searches: {
    total_saved_searches: number;
    users_with_saved_searches: number;
    stale_or_problem: number;
    searches_with_new_matches: number;
  };
  watchlist: {
    total_tracked_lots: number;
    users_with_tracked_lots: number;
    unseen_updates: number;
    stale_or_problem: number;
  };
  push: {
    total_subscriptions: number;
    users_with_push: number;
    users_without_push: number;
  };
  system: {
    live_sync_status: string;
    stale: boolean;
    last_success_at: string | null;
    last_failure_at: string | null;
    last_error_message: string | null;
  };
};

export type AdminSystemHealth = {
  generated_at: string;
  app_name: string;
  environment: string;
  live_sync: LiveSyncStatus;
  blocked_users: number;
  expired_pending_invites: number;
  provider_reconnect_required: number;
  saved_search_attention: number;
  watchlist_attention: number;
};

export type AdminUserDirectoryRow = {
  id: string;
  email: string;
  role: UserRole;
  status: string;
  created_at: string;
  updated_at: string;
  last_login_at: string | null;
  provider_state: string;
  counts: {
    provider_connections: number;
    saved_searches: number;
    tracked_lots: number;
    push_subscriptions: number;
  };
  flags: {
    has_pending_invite: boolean;
    has_reconnect_required_provider: boolean;
    has_unseen_watchlist_updates: boolean;
  };
};

export type AdminUsersResponse = {
  items: AdminUserDirectoryRow[];
  total: number;
  page: number;
  page_size: number;
};

export type AdminSavedSearchSummary = {
  id: string;
  label: string;
  providers: AuctionProvider[];
  result_count: number | null;
  cached_result_count: number | null;
  new_count: number;
  last_synced_at: string | null;
  freshness: FreshnessEnvelope;
  refresh_state: RefreshState;
  created_at: string;
};

export type AdminTrackedLotSummary = {
  id: string;
  provider: AuctionProvider;
  lot_key: string;
  lot_number: string;
  title: string;
  status: string;
  raw_status: string;
  current_bid: number | null;
  buy_now_price: number | null;
  currency: string;
  sale_date: string | null;
  last_checked_at: string | null;
  freshness: FreshnessEnvelope;
  refresh_state: RefreshState;
  has_unseen_update: boolean;
  latest_change_at: string | null;
  created_at: string;
};

export type AdminRecentActivity = {
  last_login_at: string | null;
  last_saved_search_at: string | null;
  last_tracked_lot_at: string | null;
  last_push_subscription_at: string | null;
  last_provider_activity_at: string | null;
  has_unseen_watchlist_updates: boolean;
};

export type AdminDangerZoneSummary = {
  provider_connections: number;
  saved_searches: number;
  tracked_lots: number;
  push_subscriptions: number;
  lot_snapshots: number;
  invites: number;
};

export type AdminUserDetail = {
  account: User & {
    created_at: string;
    updated_at: string;
    last_login_at: string | null;
  };
  counts: AdminUserDirectoryRow["counts"];
  invites: Invite[];
  provider_connections: ProviderConnection[];
  saved_searches: AdminSavedSearchSummary[];
  tracked_lots: AdminTrackedLotSummary[];
  push_subscriptions: PushSubscriptionItem[];
  recent_activity: AdminRecentActivity;
  danger_zone: AdminDangerZoneSummary;
};

export type AdminUserFilters = {
  query: string;
  role: "any" | UserRole;
  status: "any" | "active" | "blocked" | "disabled";
  provider_state: "any" | "none" | "connected" | "reconnect_required" | "disconnected" | "error";
  push_state: "any" | "has_push" | "no_push";
  saved_search_state: "any" | "has_saved_searches" | "no_saved_searches";
  watchlist_state: "any" | "has_tracked_lots" | "no_tracked_lots" | "unseen_updates";
  last_login: "any" | "24h" | "7d" | "stale" | "never";
  sort: "created_at_desc" | "created_at_asc" | "last_login_desc" | "last_login_asc" | "email_asc" | "email_desc";
  page: number;
  page_size: number;
};

export type AdminUserActionPayload = {
  provider?: AuctionProvider;
  resource_id?: string;
};

export type AdminUserActionResponse = {
  action: string;
  message: string;
  scope: "account" | "provider" | "resource" | "danger";
  user: AdminUserDetail["account"] | null;
  generated_password: string | null;
  counts: Record<string, number>;
};

export type TokenPair = {
  access_token: string;
  refresh_token: string;
  token_type: string;
};

export type WatchlistItem = {
  id: string;
  provider: AuctionProvider;
  auction_label: string;
  provider_lot_id: string;
  lot_key: string;
  lot_number: string;
  url: string | null;
  title: string;
  thumbnail_url: string | null;
  image_urls: string[];
  odometer: string | null;
  primary_damage: string | null;
  estimated_retail_value: number | null;
  has_key: boolean | null;
  drivetrain: string | null;
  highlights: string[];
  vin: string | null;
  status: string;
  raw_status: string;
  current_bid: number | null;
  buy_now_price: number | null;
  currency: string;
  sale_date: string | null;
  last_checked_at: string;
  freshness: FreshnessEnvelope;
  refresh_state: RefreshState;
  connection_diagnostic?: ProviderConnectionDiagnostic | null;
  created_at: string;
  has_unseen_update: boolean;
  latest_change_at: string | null;
  latest_changes: Record<string, { before: unknown; after: unknown }>;
};

export type WatchlistHistoryEntry = {
  snapshot: {
    id: string;
    tracked_lot_id: string;
    provider: AuctionProvider;
    provider_lot_id: string;
    lot_key: string;
    lot_number: string;
    status: string;
    raw_status: string;
    current_bid: number | null;
    buy_now_price: number | null;
    currency: string;
    sale_date: string | null;
    detected_at: string;
  };
  changes: Record<string, { before: unknown; after: unknown }>;
};

export type WatchlistHistoryResponse = {
  tracked_lot_id: string;
  entries: WatchlistHistoryEntry[];
};

export type SearchResult = {
  provider: AuctionProvider;
  auction_label: string;
  provider_lot_id: string;
  lot_key: string;
  lot_number: string;
  title: string;
  url: string | null;
  thumbnail_url: string | null;
  location: string | null;
  odometer?: string | null;
  sale_date: string | null;
  current_bid: number | null;
  buy_now_price?: number | null;
  currency: string;
  status: string;
  raw_status?: string;
  is_new?: boolean;
};

export type SavedSearchCriteria = {
  providers?: AuctionProvider[];
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
  external_url: string | null;
  external_links: Array<{ provider: AuctionProvider; label: string; url: string }>;
  result_count: number | null;
  cached_result_count: number | null;
  new_count: number;
  last_synced_at: string | null;
  freshness: FreshnessEnvelope;
  refresh_state: RefreshState;
  connection_diagnostic?: ProviderConnectionDiagnostic | null;
  connection_diagnostics?: ProviderConnectionDiagnostic[];
  created_at: string;
};

export type SearchResultsResponse = {
  results: SearchResult[];
  total_results: number;
  provider_diagnostics?: ProviderConnectionDiagnostic[];
};

export type SavedSearchResultsResponse = {
  saved_search: SavedSearch;
  results: SearchResult[];
  cached_result_count: number;
  new_count: number;
  last_synced_at: string | null;
  seen_at: string | null;
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

export type PushSubscriptionPayload = {
  endpoint: string;
  expirationTime: number | null;
  keys: {
    p256dh: string;
    auth: string;
  };
};

export type PushSubscriptionConfig = {
  enabled: boolean;
  public_key: string | null;
  reason: string | null;
};

export type PushDeliveryResult = {
  delivered: number;
  failed: number;
  removed: number;
  endpoints: string[];
};

export type LiveSyncStatus = {
  status: "available" | "degraded";
  last_success_at: string | null;
  last_success_source: string | null;
  last_failure_at: string | null;
  last_failure_source: string | null;
  last_error_message: string | null;
  stale: boolean;
};

export type SystemStatus = {
  status: string;
  service: string;
  environment: string;
  live_sync: LiveSyncStatus;
  freshness_policies?: {
    saved_searches?: {
      stale_after_seconds: number;
    };
    watchlist?: {
      stale_after_seconds: number;
    };
  };
};
