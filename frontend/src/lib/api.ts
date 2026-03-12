import type {
  Invite,
  PushSubscriptionItem,
  SearchCatalog,
  SearchResult,
  TokenPair,
  User,
  WatchlistItem,
} from "../types";
import { clearSession, loadTokens, saveTokens } from "./session";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api";

type HttpMethod = "GET" | "POST" | "DELETE";
type AuthLifecycleHandlers = {
  onTokensRefreshed?: (tokens: TokenPair) => void;
  onAuthFailed?: () => void;
};

let authLifecycleHandlers: AuthLifecycleHandlers = {};

export function configureAuthLifecycle(handlers: AuthLifecycleHandlers): void {
  authLifecycleHandlers = handlers;
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
    throw new Error(text || `HTTP ${response.status}`);
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
    year_from?: number;
    year_to?: number;
    lot_number?: string;
  },
  token: string,
): Promise<SearchResult[]> {
  const response = await request<{ results: SearchResult[] }>("/search", { method: "POST", body: payload, token });
  return response.results;
}

export async function getSearchCatalog(token: string): Promise<SearchCatalog> {
  return request<SearchCatalog>("/search/catalog", { token });
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
  return response.tracked_lot;
}

export async function addLotNumberToWatchlist(lotNumber: string, token: string): Promise<WatchlistItem> {
  const response = await request<{ tracked_lot: WatchlistItem }>("/watchlist", {
    method: "POST",
    body: { lot_number: lotNumber },
    token,
  });
  return response.tracked_lot;
}

export async function addFromSearch(lotUrl: string, token: string): Promise<WatchlistItem> {
  const response = await request<{ tracked_lot: WatchlistItem }>("/search/watchlist", {
    method: "POST",
    body: { lot_url: lotUrl },
    token,
  });
  return response.tracked_lot;
}

export async function listWatchlist(token: string): Promise<WatchlistItem[]> {
  const response = await request<{ items: WatchlistItem[] }>("/watchlist", { token });
  return response.items;
}

export async function removeWatchlistItem(id: string, token: string): Promise<void> {
  await request<void>(`/watchlist/${id}`, { method: "DELETE", token });
}

export async function listPushSubscriptions(token: string): Promise<PushSubscriptionItem[]> {
  const response = await request<{ items: PushSubscriptionItem[] }>("/notifications/subscriptions", { token });
  return response.items;
}

export async function subscribeToPush(subscription: PushSubscription, userAgent: string, token: string): Promise<PushSubscriptionItem> {
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
