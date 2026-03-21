import type {
  FreshnessEnvelope,
  Invite,
  PushDeliveryResult,
  PushSubscriptionConfig,
  PushSubscriptionItem,
  PushSubscriptionPayload,
  RefreshState,
  SavedSearch,
  SavedSearchResultsResponse,
  SearchCatalog,
  SearchResult,
  SearchResultsResponse,
  SystemStatus,
  TokenPair,
  User,
  WatchlistItem,
} from "../types";
import { clearSession, loadTokens, saveTokens } from "./session";

function getApiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL;
  if (configured) {
    return configured;
  }
  if (typeof window === "undefined") {
    return "http://localhost:8000/api";
  }

  const current = new URL(window.location.origin);
  if (current.protocol !== "http:" && current.protocol !== "https:") {
    return "http://localhost:8000/api";
  }

  current.port = "8000";
  current.pathname = "/api";
  current.search = "";
  current.hash = "";
  return current.toString().replace(/\/$/, "");
}

const API_BASE_URL = getApiBaseUrl();
const DEFAULT_SAVED_SEARCH_STALE_AFTER_SECONDS = 15 * 60;
const DEFAULT_WATCHLIST_STALE_AFTER_SECONDS = 15 * 60;

type HttpMethod = "GET" | "POST" | "DELETE";
type AuthLifecycleHandlers = {
  onTokensRefreshed?: (tokens: TokenPair) => void;
  onAuthFailed?: () => void;
};

let authLifecycleHandlers: AuthLifecycleHandlers = {};

export function configureAuthLifecycle(handlers: AuthLifecycleHandlers): void {
  authLifecycleHandlers = handlers;
}

function parseErrorMessage(body: string, status: number): string {
  if (!body) {
    return `HTTP ${status}`;
  }
  try {
    const parsed = JSON.parse(body) as { detail?: string };
    if (typeof parsed.detail === "string" && parsed.detail.trim()) {
      return parsed.detail;
    }
  } catch {
    return body;
  }
  return body;
}

function toIsoTimestamp(value: Date): string {
  return value.toISOString().replace(".000Z", "Z");
}

function addSeconds(value: string | null, seconds: number): string | null {
  if (!value) {
    return null;
  }
  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) {
    return null;
  }
  return toIsoTimestamp(new Date(timestamp.getTime() + seconds * 1000));
}

function normalizeFreshness(
  freshness: FreshnessEnvelope | undefined,
  fallbackLastSyncedAt: string | null,
  staleAfterSeconds: number,
): FreshnessEnvelope {
  if (freshness) {
    return {
      status: freshness.status,
      last_synced_at: freshness.last_synced_at ?? fallbackLastSyncedAt,
      stale_after: freshness.stale_after ?? addSeconds(freshness.last_synced_at ?? fallbackLastSyncedAt, staleAfterSeconds),
      degraded_reason: freshness.degraded_reason ?? null,
      retryable: Boolean(freshness.retryable),
    };
  }

  return {
    status: fallbackLastSyncedAt ? "live" : "unknown",
    last_synced_at: fallbackLastSyncedAt,
    stale_after: addSeconds(fallbackLastSyncedAt, staleAfterSeconds),
    degraded_reason: null,
    retryable: false,
  };
}

function normalizeRefreshState(
  refreshState: RefreshState | undefined,
  fallbackLastSucceededAt: string | null,
): RefreshState {
  if (refreshState) {
    return {
      status: refreshState.status,
      last_attempted_at: refreshState.last_attempted_at ?? null,
      last_succeeded_at: refreshState.last_succeeded_at ?? fallbackLastSucceededAt,
      next_retry_at: refreshState.next_retry_at ?? null,
      error_message: refreshState.error_message ?? null,
      retryable: Boolean(refreshState.retryable),
      priority_class: refreshState.priority_class ?? null,
      last_outcome: refreshState.last_outcome ?? null,
      metrics: refreshState.metrics ?? {},
    };
  }

  return {
    status: "idle",
    last_attempted_at: fallbackLastSucceededAt,
    last_succeeded_at: fallbackLastSucceededAt,
    next_retry_at: null,
    error_message: null,
    retryable: false,
    priority_class: null,
    last_outcome: fallbackLastSucceededAt ? "refreshed" : null,
    metrics: {},
  };
}

function normalizeSavedSearch(item: SavedSearch): SavedSearch {
  return {
    ...item,
    freshness: normalizeFreshness(item.freshness, item.last_synced_at, DEFAULT_SAVED_SEARCH_STALE_AFTER_SECONDS),
    refresh_state: normalizeRefreshState(item.refresh_state, item.last_synced_at),
  };
}

function normalizeWatchlistItem(item: WatchlistItem): WatchlistItem {
  return {
    ...item,
    freshness: normalizeFreshness(item.freshness, item.last_checked_at, DEFAULT_WATCHLIST_STALE_AFTER_SECONDS),
    refresh_state: normalizeRefreshState(item.refresh_state, item.last_checked_at),
  };
}

function normalizeSavedSearchResultsResponse(response: SavedSearchResultsResponse): SavedSearchResultsResponse {
  return {
    ...response,
    saved_search: normalizeSavedSearch(response.saved_search),
  };
}

function normalizeSystemStatus(response: SystemStatus): SystemStatus {
  return {
    ...response,
    freshness_policies: {
      saved_searches: response.freshness_policies?.saved_searches ?? {
        stale_after_seconds: DEFAULT_SAVED_SEARCH_STALE_AFTER_SECONDS,
      },
      watchlist: response.freshness_policies?.watchlist ?? {
        stale_after_seconds: DEFAULT_WATCHLIST_STALE_AFTER_SECONDS,
      },
    },
  };
}

async function refreshTokens(): Promise<TokenPair | null> {
  const stored = loadTokens();
  if (!stored?.refresh_token) {
    return null;
  }

  const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: stored.refresh_token }),
  });

  if (!response.ok) {
    clearSession();
    authLifecycleHandlers.onAuthFailed?.();
    return null;
  }

  const refreshed = (await response.json()) as TokenPair;
  saveTokens(refreshed);
  authLifecycleHandlers.onTokensRefreshed?.(refreshed);
  return refreshed;
}

async function request<T>(
  path: string,
  options: { method?: HttpMethod; body?: unknown; token?: string; retryOnUnauthorized?: boolean } = {},
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: options.method ?? "GET",
    headers: {
      "Content-Type": "application/json",
      ...(options.token ? { Authorization: `Bearer ${options.token}` } : {}),
    },
    body: options.body ? JSON.stringify(options.body) : undefined,
  });

  if (response.status === 401 && options.token && options.retryOnUnauthorized !== false) {
    const refreshed = await refreshTokens();
    if (refreshed) {
      return request<T>(path, { ...options, token: refreshed.access_token, retryOnUnauthorized: false });
    }
    throw new Error("Session expired. Please sign in again.");
  }

  if (!response.ok) {
    const text = await response.text();
    throw new Error(parseErrorMessage(text, response.status));
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

function decodeJwtPayload(token: string): Record<string, unknown> {
  const [, payload] = token.split(".");
  const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
  return JSON.parse(atob(padded)) as Record<string, unknown>;
}

export function deriveUserFromAccessToken(token: string, email: string): User {
  const payload = decodeJwtPayload(token);
  return {
    id: String(payload.sub),
    email,
    role: String(payload.role) as User["role"],
    status: "active",
  };
}

export async function login(email: string, password: string): Promise<{ tokens: TokenPair; user: User }> {
  const tokens = await request<TokenPair>("/auth/login", {
    method: "POST",
    body: { email, password },
  });
  return { tokens, user: deriveUserFromAccessToken(tokens.access_token, email) };
}

export async function acceptInvite(token: string, password: string): Promise<User> {
  const response = await request<{ user: User }>("/auth/invites/accept", {
    method: "POST",
    body: { token, password },
  });
  return response.user;
}

export async function createInvite(email: string, token: string): Promise<Invite> {
  return request<Invite>("/admin/invites", { method: "POST", body: { email }, token });
}

export async function searchLots(
  payload: {
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
  },
  token: string,
): Promise<SearchResultsResponse> {
  return request<SearchResultsResponse>("/search", { method: "POST", body: payload, token });
}

export async function getSearchCatalog(token: string): Promise<SearchCatalog> {
  return request<SearchCatalog>("/search/catalog", { token });
}

export async function getSystemStatus(token: string): Promise<SystemStatus> {
  return normalizeSystemStatus(await request<SystemStatus>("/system/status", { token }));
}

export async function listSavedSearches(token: string): Promise<SavedSearch[]> {
  const response = await request<{ items: SavedSearch[] }>("/search/saved", { token });
  return response.items.map(normalizeSavedSearch);
}

export async function saveSearch(
  payload: {
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
    label?: string;
    result_count?: number;
    seed_results?: SearchResult[];
  },
  token: string,
): Promise<SavedSearch> {
  const response = await request<{ saved_search: SavedSearch }>("/search/saved", {
    method: "POST",
    body: payload,
    token,
  });
  return normalizeSavedSearch(response.saved_search);
}

export async function deleteSavedSearch(id: string, token: string): Promise<void> {
  await request<void>(`/search/saved/${id}`, { method: "DELETE", token });
}

export async function viewSavedSearch(id: string, token: string): Promise<SavedSearchResultsResponse> {
  return normalizeSavedSearchResultsResponse(
    await request<SavedSearchResultsResponse>(`/search/saved/${id}/view`, { method: "POST", token }),
  );
}

export async function refreshSavedSearchLive(id: string, token: string): Promise<SavedSearchResultsResponse> {
  return normalizeSavedSearchResultsResponse(
    await request<SavedSearchResultsResponse>(`/search/saved/${id}/refresh-live`, { method: "POST", token }),
  );
}

export async function refreshSearchCatalog(token: string): Promise<SearchCatalog> {
  return request<SearchCatalog>("/admin/search-catalog/refresh", { method: "POST", token });
}

export async function addToWatchlist(lotUrl: string, token: string): Promise<WatchlistItem> {
  const response = await request<{ tracked_lot: WatchlistItem }>("/watchlist", {
    method: "POST",
    body: { lot_url: lotUrl },
    token,
  });
  return normalizeWatchlistItem(response.tracked_lot);
}

export async function addLotNumberToWatchlist(lotNumber: string, token: string): Promise<WatchlistItem> {
  const response = await request<{ tracked_lot: WatchlistItem }>("/watchlist", {
    method: "POST",
    body: { lot_number: lotNumber },
    token,
  });
  return normalizeWatchlistItem(response.tracked_lot);
}

export async function addFromSearch(lotUrl: string, token: string): Promise<WatchlistItem> {
  const response = await request<{ tracked_lot: WatchlistItem }>("/search/watchlist", {
    method: "POST",
    body: { lot_url: lotUrl },
    token,
  });
  return normalizeWatchlistItem(response.tracked_lot);
}

export async function listWatchlist(token: string): Promise<WatchlistItem[]> {
  const response = await request<{ items: WatchlistItem[] }>("/watchlist", { token });
  return response.items.map(normalizeWatchlistItem);
}

export async function refreshWatchlistLotLive(id: string, token: string): Promise<WatchlistItem> {
  const response = await request<{ tracked_lot: WatchlistItem }>(`/watchlist/${id}/refresh-live`, {
    method: "POST",
    token,
  });
  return normalizeWatchlistItem(response.tracked_lot);
}

export async function removeWatchlistItem(id: string, token: string): Promise<void> {
  await request<void>(`/watchlist/${id}`, { method: "DELETE", token });
}

export async function listPushSubscriptions(token: string): Promise<PushSubscriptionItem[]> {
  const response = await request<{ items: PushSubscriptionItem[] }>("/notifications/subscriptions", { token });
  return response.items;
}

export async function getPushSubscriptionConfig(token: string): Promise<PushSubscriptionConfig> {
  return request<PushSubscriptionConfig>("/notifications/subscription-config", { token });
}

export async function subscribeToPush(
  subscription: PushSubscriptionPayload,
  userAgent: string,
  token: string,
): Promise<PushSubscriptionItem> {
  return request<PushSubscriptionItem>("/notifications/subscriptions", {
    method: "POST",
    body: { subscription, user_agent: userAgent },
    token,
  });
}

export async function unsubscribeFromPush(endpoint: string, token: string): Promise<void> {
  const query = new URLSearchParams({ endpoint }).toString();
  await request<void>(`/notifications/subscriptions?${query}`, { method: "DELETE", token });
}

export async function sendPushTest(token: string): Promise<PushDeliveryResult> {
  return request<PushDeliveryResult>("/notifications/test", {
    method: "POST",
    body: {
      title: "CarTrap test notification",
      body: "Push delivery is working on this device.",
    },
    token,
  });
}
