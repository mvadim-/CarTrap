import { useEffect, useRef, useState, type CSSProperties } from "react";

import { useHashRoute } from "./app/router";
import { useSession } from "./app/useSession";
import { AdminInvitesPanel } from "./features/admin/AdminInvitesPanel";
import { AdminSearchCatalogPanel } from "./features/admin/AdminSearchCatalogPanel";
import { InviteAcceptScreen } from "./features/auth/InviteAcceptScreen";
import { LoginScreen } from "./features/auth/LoginScreen";
import { AccountMenuSheet } from "./features/dashboard/AccountMenuSheet";
import { DashboardShell } from "./features/dashboard/DashboardShell";
import { PushSettingsModal } from "./features/push/PushSettingsModal";
import { SearchPanel } from "./features/search/SearchPanel";
import { AsyncStatus } from "./features/shared/AsyncStatus";
import { WatchlistPanel } from "./features/watchlist/WatchlistPanel";
import {
  acceptInvite,
  addFromSearch,
  addLotNumberToWatchlist,
  connectCopartConnection,
  configureAuthLifecycle,
  createInvite,
  deleteSavedSearch,
  disconnectCopartConnection,
  getPushSubscriptionConfig,
  getSearchCatalog,
  getSystemStatus,
  listProviderConnections,
  listPushSubscriptions,
  listSavedSearches,
  listWatchlist,
  login,
  reconnectCopartConnection,
  refreshWatchlistLotLive,
  refreshSavedSearchLive,
  refreshSearchCatalog,
  removeWatchlistItem,
  saveSearch,
  searchLots,
  sendPushTest,
  subscribeToPush,
  unsubscribeFromPush,
  viewSavedSearch,
} from "./lib/api";
import type {
  Invite,
  LiveSyncStatus,
  ProviderConnection,
  ProviderConnectionDiagnostic,
  PushDeliveryResult,
  PushSubscriptionConfig,
  PushSubscriptionItem,
  PushSubscriptionPayload,
  ReliabilityDiagnostics,
  SavedSearch,
  SavedSearchResultsResponse,
  SearchCatalog,
  SearchResult,
  WatchlistItem,
} from "./types";

type SearchPayload = {
  make?: string;
  model?: string;
  makeFilter?: string;
  modelFilter?: string;
  driveType?: string;
  primaryDamage?: string;
  titleType?: string;
  fuelType?: string;
  lotCondition?: string;
  odometerRange?: string;
  yearFrom?: string;
  yearTo?: string;
};

type DashboardResourceKey = "watchlist" | "savedSearches" | "subscriptions" | "searchCatalog" | "liveSync";
type DashboardState<T> = Record<DashboardResourceKey, T>;
type PushRefreshTarget = DashboardResourceKey;
type PullToRefreshPhase = "idle" | "pulling" | "armed" | "refreshing";

type ActionState = {
  isSearching: boolean;
  isSavingSearch: boolean;
  openingSavedSearchId: string | null;
  refreshingSavedSearchId: string | null;
  deletingSavedSearchId: string | null;
  addingFromSearchLotUrl: string | null;
  isAddingWatchlistLot: boolean;
  refreshingWatchlistId: string | null;
  removingWatchlistId: string | null;
  isSubscribingPush: boolean;
  unsubscribingEndpoint: string | null;
  isSendingPushTest: boolean;
  isCreatingInvite: boolean;
  isRefreshingCatalog: boolean;
};

const INITIAL_DASHBOARD_LOADING: DashboardState<boolean> = {
  watchlist: false,
  savedSearches: false,
  subscriptions: false,
  searchCatalog: false,
  liveSync: false,
};

const INITIAL_DASHBOARD_ERRORS: DashboardState<string | null> = {
  watchlist: null,
  savedSearches: null,
  subscriptions: null,
  searchCatalog: null,
  liveSync: null,
};

const INITIAL_ACTION_STATE: ActionState = {
  isSearching: false,
  isSavingSearch: false,
  openingSavedSearchId: null,
  refreshingSavedSearchId: null,
  deletingSavedSearchId: null,
  addingFromSearchLotUrl: null,
  isAddingWatchlistLot: false,
  refreshingWatchlistId: null,
  removingWatchlistId: null,
  isSubscribingPush: false,
  unsubscribingEndpoint: null,
  isSendingPushTest: false,
  isCreatingInvite: false,
  isRefreshingCatalog: false,
};

const PUSH_MESSAGE_TYPE = "cartrap:push-received";
const APP_TITLE = "CarTrap";
const AUTO_REFRESH_INTERVAL_MS = 60_000;
const TAB_ATTENTION_BLINK_MS = 1_000;
const MOBILE_PULL_TO_REFRESH_MAX_WIDTH = 900;
const PULL_TO_REFRESH_THRESHOLD = 72;
const PULL_TO_REFRESH_MAX_OFFSET = 104;
const OPERATIONAL_REFRESH_TARGETS: PushRefreshTarget[] = ["watchlist", "savedSearches", "liveSync"];

type DashboardLoaderOptions = {
  silent?: boolean;
};

function isDashboardResourceKey(value: string): value is DashboardResourceKey {
  return ["watchlist", "savedSearches", "subscriptions", "searchCatalog", "liveSync"].includes(value);
}

function normalizePushRefreshTargets(value: unknown): PushRefreshTarget[] {
  let rawTargets = value;
  if (!Array.isArray(rawTargets) && rawTargets && typeof rawTargets === "object") {
    const nestedTargets = rawTargets as Record<string, unknown>;
    rawTargets = nestedTargets.targets ?? nestedTargets.items ?? nestedTargets.resources ?? null;
  }
  if (!Array.isArray(rawTargets)) {
    return [];
  }
  return rawTargets.filter((item): item is PushRefreshTarget => typeof item === "string" && isDashboardResourceKey(item));
}

function getNotificationPermission(): string {
  return typeof Notification === "undefined" ? "unsupported" : Notification.permission;
}

function getBrowserOfflineState(): boolean {
  return typeof navigator !== "undefined" && "onLine" in navigator ? !navigator.onLine : false;
}

function isDocumentHidden(): boolean {
  return typeof document !== "undefined" && document.visibilityState === "hidden";
}

function getVerticalScrollOffset(): number {
  if (typeof window === "undefined" || typeof document === "undefined") {
    return 0;
  }
  return Math.max(window.scrollY, document.documentElement.scrollTop, document.body.scrollTop, 0);
}

function supportsMobilePullToRefresh(): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  const hasCoarsePointer =
    typeof window.matchMedia === "function" ? window.matchMedia("(pointer: coarse)").matches : "ontouchstart" in window;
  return hasCoarsePointer && window.innerWidth <= MOBILE_PULL_TO_REFRESH_MAX_WIDTH;
}

function getPullToRefreshOffset(deltaY: number): number {
  if (deltaY <= 0) {
    return 0;
  }
  return Math.min(PULL_TO_REFRESH_MAX_OFFSET, Math.round(deltaY * 0.55));
}

function toErrorMessage(caught: unknown, fallbackMessage: string): string {
  return caught instanceof Error && caught.message.trim() ? caught.message : fallbackMessage;
}

function pluralize(value: number, singular: string, plural: string): string {
  return value === 1 ? singular : plural;
}

function countWatchlistUpdates(previousItems: WatchlistItem[], nextItems: WatchlistItem[]): number {
  const previousById = new Map(previousItems.map((item) => [item.id, item]));
  let updates = 0;

  for (const item of nextItems) {
    const previous = previousById.get(item.id);
    if (!previous) {
      updates += 1;
      continue;
    }

    const latestChangesDiffer = JSON.stringify(previous.latest_changes) !== JSON.stringify(item.latest_changes);
    const changed =
      previous.latest_change_at !== item.latest_change_at ||
      (item.has_unseen_update && !previous.has_unseen_update) ||
      previous.status !== item.status ||
      previous.raw_status !== item.raw_status ||
      previous.current_bid !== item.current_bid ||
      previous.buy_now_price !== item.buy_now_price ||
      previous.sale_date !== item.sale_date ||
      latestChangesDiffer;

    if (changed) {
      updates += 1;
    }
  }

  return updates;
}

function getWatchlistSaleTimestamp(item: WatchlistItem): number {
  if (!item.sale_date) {
    return Number.POSITIVE_INFINITY;
  }
  const saleTimestamp = new Date(item.sale_date).getTime();
  return Number.isNaN(saleTimestamp) ? Number.POSITIVE_INFINITY : saleTimestamp;
}

function sortWatchlistItems(items: WatchlistItem[]): WatchlistItem[] {
  return [...items].sort((left, right) => {
    const saleDifference = getWatchlistSaleTimestamp(left) - getWatchlistSaleTimestamp(right);
    if (saleDifference !== 0) {
      return saleDifference;
    }

    const createdDifference = new Date(left.created_at).getTime() - new Date(right.created_at).getTime();
    if (!Number.isNaN(createdDifference) && createdDifference !== 0) {
      return createdDifference;
    }

    return left.lot_number.localeCompare(right.lot_number);
  });
}

function countSavedSearchUpdates(
  previousItems: SavedSearch[],
  nextItems: SavedSearch[],
): { newMatches: number; refreshedSearches: number } {
  const previousById = new Map(previousItems.map((item) => [item.id, item]));
  let newMatches = 0;
  let refreshedSearches = 0;

  for (const item of nextItems) {
    const previous = previousById.get(item.id);
    if (!previous) {
      if (item.new_count > 0) {
        newMatches += item.new_count;
      } else {
        refreshedSearches += 1;
      }
      continue;
    }

    const nextNewMatches = Math.max(item.new_count - previous.new_count, 0);
    if (nextNewMatches > 0) {
      newMatches += nextNewMatches;
      continue;
    }

    const refreshed =
      previous.result_count !== item.result_count ||
      previous.cached_result_count !== item.cached_result_count ||
      previous.last_synced_at !== item.last_synced_at;

    if (refreshed) {
      refreshedSearches += 1;
    }
  }

  return { newMatches, refreshedSearches };
}

function buildReliabilitySummary<T extends { freshness: { status: string }; refresh_state: { status: string } }>(
  items: T[],
) {
  return items.reduce(
    (summary, item) => {
      summary.total += 1;
      if (item.refresh_state.status === "retryable_failure") {
        summary.retryable_failures += 1;
      }
      if (item.refresh_state.status === "repair_pending") {
        summary.repair_pending += 1;
      }
      if (item.refresh_state.status === "failed") {
        summary.failed += 1;
      }
      if (item.freshness.status === "outdated") {
        summary.outdated += 1;
      }
      if (item.freshness.status === "degraded") {
        summary.degraded += 1;
      }
      if (item.freshness.status === "cached") {
        summary.cached += 1;
      }
      if (
        item.refresh_state.status !== "idle" ||
        item.freshness.status === "outdated" ||
        item.freshness.status === "degraded" ||
        item.freshness.status === "unknown"
      ) {
        summary.attention += 1;
      }
      return summary;
    },
    {
      total: 0,
      attention: 0,
      retryable_failures: 0,
      repair_pending: 0,
      failed: 0,
      outdated: 0,
      degraded: 0,
      cached: 0,
    },
  );
}

function buildReliabilityDiagnostics(savedSearches: SavedSearch[], watchlist: WatchlistItem[]): ReliabilityDiagnostics {
  const savedSearchSummary = buildReliabilitySummary(savedSearches);
  const watchlistSummary = buildReliabilitySummary(watchlist);
  return {
    saved_searches: savedSearchSummary,
    watchlist: watchlistSummary,
    total_attention: savedSearchSummary.attention + watchlistSummary.attention,
  };
}

function buildTabAttentionMessage(
  previousWatchlist: WatchlistItem[],
  nextWatchlist: WatchlistItem[] | null,
  previousSavedSearches: SavedSearch[],
  nextSavedSearches: SavedSearch[] | null,
): string | null {
  const watchlistUpdates = nextWatchlist ? countWatchlistUpdates(previousWatchlist, nextWatchlist) : 0;
  const savedSearchUpdates = nextSavedSearches
    ? countSavedSearchUpdates(previousSavedSearches, nextSavedSearches)
    : { newMatches: 0, refreshedSearches: 0 };

  const parts: string[] = [];
  if (watchlistUpdates > 0) {
    parts.push(`${watchlistUpdates} tracked lot ${pluralize(watchlistUpdates, "update", "updates")}`);
  }
  if (savedSearchUpdates.newMatches > 0) {
    parts.push(`${savedSearchUpdates.newMatches} new ${pluralize(savedSearchUpdates.newMatches, "match", "matches")}`);
  } else if (savedSearchUpdates.refreshedSearches > 0) {
    parts.push(
      `${savedSearchUpdates.refreshedSearches} saved ${pluralize(
        savedSearchUpdates.refreshedSearches,
        "search refreshed",
        "searches refreshed",
      )}`,
    );
  }

  if (parts.length === 0) {
    return null;
  }
  return `${parts.join(" + ")} | ${APP_TITLE}`;
}

function encodeBase64Url(buffer: ArrayBuffer | null): string {
  if (!buffer) {
    return "";
  }
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function decodeBase64Url(value: string): Uint8Array {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
  const binary = atob(padded);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

function serializePushSubscription(subscription: PushSubscription): PushSubscriptionPayload {
  const p256dh = encodeBase64Url(subscription.getKey("p256dh"));
  const auth = encodeBase64Url(subscription.getKey("auth"));
  if (!p256dh || !auth) {
    throw new Error("Browser returned an invalid push subscription.");
  }
  return {
    endpoint: subscription.endpoint,
    expirationTime: subscription.expirationTime,
    keys: { p256dh, auth },
  };
}

async function ensurePushRegistration(): Promise<ServiceWorkerRegistration> {
  if (!("serviceWorker" in navigator)) {
    throw new Error("This browser does not support service workers.");
  }
  const existingRegistration = await navigator.serviceWorker.getRegistration();
  if (existingRegistration) {
    return navigator.serviceWorker.ready;
  }
  await navigator.serviceWorker.register("/sw.js");
  return navigator.serviceWorker.ready;
}

export function App() {
  const [routeState, navigate] = useHashRoute();
  const session = useSession();
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searchTotalResults, setSearchTotalResults] = useState(0);
  const [savedSearches, setSavedSearches] = useState<SavedSearch[]>([]);
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [providerConnections, setProviderConnections] = useState<ProviderConnection[]>([]);
  const [latestInvite, setLatestInvite] = useState<Invite | null>(null);
  const [inviteLink, setInviteLink] = useState<string | null>(null);
  const [subscriptions, setSubscriptions] = useState<PushSubscriptionItem[]>([]);
  const [searchCatalog, setSearchCatalog] = useState<SearchCatalog | null>(null);
  const [permissionState, setPermissionState] = useState(getNotificationPermission());
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isAccountMenuOpen, setIsAccountMenuOpen] = useState(false);
  const [isManualSearchOpen, setIsManualSearchOpen] = useState(false);
  const [liveSyncStatus, setLiveSyncStatus] = useState<LiveSyncStatus | null>(null);
  const [pushConfig, setPushConfig] = useState<PushSubscriptionConfig | null>(null);
  const [pushConfigError, setPushConfigError] = useState<string | null>(null);
  const [isLoadingPushConfig, setIsLoadingPushConfig] = useState(false);
  const [currentPushEndpoint, setCurrentPushEndpoint] = useState<string | null>(null);
  const [isBrowserOffline, setIsBrowserOffline] = useState(getBrowserOfflineState());
  const [tabAttentionMessage, setTabAttentionMessage] = useState<string | null>(null);
  const [dashboardLoading, setDashboardLoading] = useState<DashboardState<boolean>>(INITIAL_DASHBOARD_LOADING);
  const [dashboardErrors, setDashboardErrors] = useState<DashboardState<string | null>>(INITIAL_DASHBOARD_ERRORS);
  const [actionState, setActionState] = useState<ActionState>(INITIAL_ACTION_STATE);
  const [isLoadingProviderConnections, setIsLoadingProviderConnections] = useState(false);
  const [providerConnectionsError, setProviderConnectionsError] = useState<string | null>(null);
  const [pullToRefreshOffset, setPullToRefreshOffset] = useState(0);
  const [pullToRefreshPhase, setPullToRefreshPhase] = useState<PullToRefreshPhase>("idle");
  const pushRefreshTimeoutRef = useRef<number | null>(null);
  const pendingPushRefreshTargetsRef = useRef<Set<PushRefreshTarget>>(new Set());
  const watchlistRef = useRef<WatchlistItem[]>([]);
  const savedSearchesRef = useRef<SavedSearch[]>([]);
  const pullToRefreshPhaseRef = useRef<PullToRefreshPhase>("idle");
  const pullToRefreshTouchStateRef = useRef({
    isTracking: false,
    startY: 0,
    lastOffset: 0,
  });

  const isBootstrapping = Object.values(dashboardLoading).some(Boolean);
  const supportsPush = typeof Notification !== "undefined" && typeof window !== "undefined" && "PushManager" in window;
  const isSecurePushContext = typeof window !== "undefined" ? window.isSecureContext : false;
  const isAdmin = session.user?.role === "admin";
  const isMobilePullToRefreshEnabled =
    session.isAuthenticated &&
    !isSettingsOpen &&
    !isManualSearchOpen &&
    typeof window !== "undefined" &&
    supportsMobilePullToRefresh();
  const pullToRefreshStyle = {
    "--pull-offset": `${pullToRefreshOffset}px`,
    "--pull-progress": `${Math.min(pullToRefreshOffset / PULL_TO_REFRESH_THRESHOLD, 1)}`,
  } as CSSProperties;
  const reliabilityDiagnostics = buildReliabilityDiagnostics(savedSearches, watchlist);
  const copartConnection = providerConnections.find((item) => item.provider === "copart") ?? null;
  const copartConnectionDiagnostic: ProviderConnectionDiagnostic =
    copartConnection === null || copartConnection.status === "disconnected"
      ? {
          provider: "copart",
          status: "connection_missing",
          message: "Connect Copart to enable live search and watchlist refreshes.",
          connection_id: null,
          reconnect_required: false,
        }
      : copartConnection.status === "reconnect_required"
        ? {
            provider: "copart",
            status: "reconnect_required",
            message: "Reconnect Copart from Account to restore live search and refresh actions.",
            connection_id: copartConnection.id,
            reconnect_required: true,
          }
        : {
            provider: "copart",
            status: "ready",
            message: "Copart live actions are available.",
            connection_id: copartConnection.id,
            reconnect_required: false,
          };

  useEffect(() => {
    if (!window.location.hash) {
      window.location.hash = "#/login";
    }
  }, []);

  useEffect(() => {
    function syncOnlineState() {
      setIsBrowserOffline(getBrowserOfflineState());
    }

    window.addEventListener("online", syncOnlineState);
    window.addEventListener("offline", syncOnlineState);
    return () => {
      window.removeEventListener("online", syncOnlineState);
      window.removeEventListener("offline", syncOnlineState);
    };
  }, []);

  useEffect(() => {
    watchlistRef.current = watchlist;
  }, [watchlist]);

  useEffect(() => {
    savedSearchesRef.current = savedSearches;
  }, [savedSearches]);

  useEffect(() => {
    if (!tabAttentionMessage || isDocumentHidden()) {
      return;
    }
    setTabAttentionMessage(null);
  }, [tabAttentionMessage]);

  useEffect(() => {
    if (!tabAttentionMessage || !isDocumentHidden()) {
      document.title = APP_TITLE;
      return;
    }

    let showBaseTitle = false;
    document.title = tabAttentionMessage;
    const intervalId = window.setInterval(() => {
      showBaseTitle = !showBaseTitle;
      document.title = showBaseTitle ? APP_TITLE : tabAttentionMessage;
    }, TAB_ATTENTION_BLINK_MS);

    return () => {
      window.clearInterval(intervalId);
      document.title = APP_TITLE;
    };
  }, [tabAttentionMessage]);

  function resetDashboardData() {
    setSearchResults([]);
    setSearchTotalResults(0);
    setSavedSearches([]);
    setWatchlist([]);
    setProviderConnections([]);
    setSubscriptions([]);
    setSearchCatalog(null);
    setLiveSyncStatus(null);
    setPushConfig(null);
    setPushConfigError(null);
    setCurrentPushEndpoint(null);
    setLatestInvite(null);
    setInviteLink(null);
    setDashboardErrors(INITIAL_DASHBOARD_ERRORS);
    setDashboardLoading(INITIAL_DASHBOARD_LOADING);
    setActionState(INITIAL_ACTION_STATE);
    setIsLoadingProviderConnections(false);
    setProviderConnectionsError(null);
    setIsAccountMenuOpen(false);
    setIsSettingsOpen(false);
    setIsManualSearchOpen(false);
    setTabAttentionMessage(null);
    setPullToRefreshOffset(0);
    setPullToRefreshPhase("idle");
  }

  function setDashboardLoadingState(key: DashboardResourceKey, value: boolean) {
    setDashboardLoading((current) => ({ ...current, [key]: value }));
  }

  function setDashboardErrorState(key: DashboardResourceKey, value: string | null) {
    setDashboardErrors((current) => ({ ...current, [key]: value }));
  }

  async function runDashboardLoader<T>(
    key: DashboardResourceKey,
    fallbackMessage: string,
    loader: () => Promise<T>,
    options: DashboardLoaderOptions = {},
  ): Promise<T | null> {
    if (!options.silent) {
      setDashboardLoadingState(key, true);
    }
    try {
      const result = await loader();
      setDashboardErrorState(key, null);
      return result;
    } catch (caught) {
      setDashboardErrorState(key, toErrorMessage(caught, fallbackMessage));
      return null;
    } finally {
      if (!options.silent) {
        setDashboardLoadingState(key, false);
      }
    }
  }

  async function loadWatchlistResource(token: string, options: DashboardLoaderOptions = {}) {
    return runDashboardLoader("watchlist", "Could not load tracked lots.", async () => {
      const items = sortWatchlistItems(await listWatchlist(token));
      setWatchlist(items);
      return items;
    }, options);
  }

  async function loadSavedSearchesResource(token: string, options: DashboardLoaderOptions = {}) {
    return runDashboardLoader("savedSearches", "Could not load saved searches.", async () => {
      const items = await listSavedSearches(token);
      setSavedSearches(items);
      return items;
    }, options);
  }

  async function loadPushSubscriptionsResource(token: string, options: DashboardLoaderOptions = {}) {
    return runDashboardLoader("subscriptions", "Could not load device subscriptions.", async () => {
      const items = await listPushSubscriptions(token);
      setSubscriptions(items);
      return items;
    }, options);
  }

  async function loadProviderConnectionsResource(token: string): Promise<ProviderConnection[] | null> {
    setIsLoadingProviderConnections(true);
    try {
      const items = await listProviderConnections(token);
      setProviderConnections(items);
      setProviderConnectionsError(null);
      return items;
    } catch (caught) {
      setProviderConnectionsError(toErrorMessage(caught, "Could not load provider connections."));
      return null;
    } finally {
      setIsLoadingProviderConnections(false);
    }
  }

  async function loadSearchCatalogResource(token: string, options: DashboardLoaderOptions = {}) {
    return runDashboardLoader("searchCatalog", "Could not load the search catalog.", async () => {
      const catalog = await getSearchCatalog(token);
      setSearchCatalog(catalog);
      return catalog;
    }, options);
  }

  async function loadLiveSyncStatusResource(token: string, options: DashboardLoaderOptions = {}) {
    return runDashboardLoader("liveSync", "Could not load live-sync status.", async () => {
      const status = await getSystemStatus(token);
      setLiveSyncStatus(status.live_sync);
      return status;
    }, options);
  }

  async function loadPushConfigResource(token: string): Promise<PushSubscriptionConfig | null> {
    setIsLoadingPushConfig(true);
    try {
      const config = await getPushSubscriptionConfig(token);
      setPushConfig(config);
      setPushConfigError(null);
      return config;
    } catch (caught) {
      const message = toErrorMessage(caught, "Could not load push diagnostics.");
      setPushConfigError(message);
      return null;
    } finally {
      setIsLoadingPushConfig(false);
    }
  }

  async function detectCurrentPushSubscriptionEndpoint(): Promise<string | null> {
    if (!("serviceWorker" in navigator)) {
      setCurrentPushEndpoint(null);
      return null;
    }
    try {
      const registration = await navigator.serviceWorker.getRegistration();
      const subscription = await registration?.pushManager.getSubscription();
      const endpoint = subscription?.endpoint ?? null;
      setCurrentPushEndpoint(endpoint);
      return endpoint;
    } catch {
      setCurrentPushEndpoint(null);
      return null;
    }
  }

  async function refreshResources(
    token: string,
    targets: PushRefreshTarget[],
    options: DashboardLoaderOptions & { allowTabAttention?: boolean } = {},
  ) {
    const uniqueTargets = Array.from(new Set(targets));
    const previousWatchlist = watchlistRef.current;
    const previousSavedSearches = savedSearchesRef.current;
    let nextWatchlist: WatchlistItem[] | null = null;
    let nextSavedSearches: SavedSearch[] | null = null;

    await Promise.allSettled(
      uniqueTargets.map((target) => {
        switch (target) {
          case "watchlist":
            return loadWatchlistResource(token, options).then((items) => {
              nextWatchlist = items;
            });
          case "savedSearches":
            return loadSavedSearchesResource(token, options).then((items) => {
              nextSavedSearches = items;
            });
          case "subscriptions":
            return loadPushSubscriptionsResource(token, options).then(() => undefined);
          case "searchCatalog":
            return loadSearchCatalogResource(token, options).then(() => undefined);
          case "liveSync":
            return loadLiveSyncStatusResource(token, options).then(() => undefined);
          default:
            return Promise.resolve();
        }
      }),
    );

    if (options.allowTabAttention && isDocumentHidden()) {
      const nextMessage = buildTabAttentionMessage(
        previousWatchlist,
        nextWatchlist,
        previousSavedSearches,
        nextSavedSearches,
      );
      if (nextMessage) {
        setTabAttentionMessage(nextMessage);
      }
    }
  }

  async function loadDashboardResources(token: string) {
    await Promise.allSettled([
      loadWatchlistResource(token),
      loadSavedSearchesResource(token),
      loadProviderConnectionsResource(token),
      loadPushSubscriptionsResource(token),
      loadSearchCatalogResource(token),
      loadLiveSyncStatusResource(token),
    ]);
  }

  async function refreshDashboardFromPull(token: string) {
    setPullToRefreshPhase("refreshing");
    setPullToRefreshOffset(PULL_TO_REFRESH_THRESHOLD);
    try {
      await loadDashboardResources(token);
    } finally {
      setPullToRefreshOffset(0);
      setPullToRefreshPhase("idle");
    }
  }

  useEffect(() => {
    configureAuthLifecycle({
      onTokensRefreshed: session.updateTokens,
      onAuthFailed: () => {
        session.logout();
        resetDashboardData();
        setGlobalError("Session expired. Please sign in again.");
        navigate("/login");
      },
    });
  }, [navigate, session]);

  useEffect(() => {
    const accessToken = session.accessToken;
    if (!accessToken) {
      return;
    }
    void loadDashboardResources(accessToken);
  }, [session.accessToken]);

  useEffect(() => {
    const accessToken = session.accessToken;
    if (!accessToken || isBrowserOffline) {
      return;
    }

    const intervalId = window.setInterval(() => {
      void refreshResources(accessToken, OPERATIONAL_REFRESH_TARGETS, {
        silent: true,
        allowTabAttention: true,
      });
    }, AUTO_REFRESH_INTERVAL_MS);

    return () => window.clearInterval(intervalId);
  }, [isBrowserOffline, session.accessToken]);

  useEffect(() => {
    const accessToken = session.accessToken;
    if (!accessToken) {
      return;
    }

    function handleWindowFocus() {
      setTabAttentionMessage(null);
      if (isBrowserOffline) {
        return;
      }
      void refreshResources(accessToken, OPERATIONAL_REFRESH_TARGETS, { silent: true });
    }

    function handleVisibilityChange() {
      if (isDocumentHidden()) {
        return;
      }
      setTabAttentionMessage(null);
      if (isBrowserOffline) {
        return;
      }
      void refreshResources(accessToken, OPERATIONAL_REFRESH_TARGETS, { silent: true });
    }

    window.addEventListener("focus", handleWindowFocus);
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      window.removeEventListener("focus", handleWindowFocus);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [isBrowserOffline, session.accessToken]);

  useEffect(() => {
    pullToRefreshPhaseRef.current = pullToRefreshPhase;
  }, [pullToRefreshPhase]);

  useEffect(() => {
    if (!session.isAuthenticated || !session.accessToken || isSettingsOpen || isManualSearchOpen) {
      setPullToRefreshOffset(0);
      if (pullToRefreshPhaseRef.current !== "refreshing") {
        setPullToRefreshPhase("idle");
      }
      return;
    }

    function resetGestureState() {
      pullToRefreshTouchStateRef.current.isTracking = false;
      pullToRefreshTouchStateRef.current.startY = 0;
      pullToRefreshTouchStateRef.current.lastOffset = 0;
      setPullToRefreshOffset(0);
      setPullToRefreshPhase("idle");
    }

    function handleTouchStart(event: TouchEvent) {
      if (
        !supportsMobilePullToRefresh() ||
        pullToRefreshPhaseRef.current === "refreshing" ||
        event.touches.length !== 1 ||
        getVerticalScrollOffset() > 0
      ) {
        return;
      }
      const target = event.target;
      if (target instanceof Element && target.closest(".modal-card")) {
        return;
      }
      pullToRefreshTouchStateRef.current.isTracking = true;
      pullToRefreshTouchStateRef.current.startY = event.touches[0]?.clientY ?? 0;
      pullToRefreshTouchStateRef.current.lastOffset = 0;
    }

    function handleTouchMove(event: TouchEvent) {
      if (!pullToRefreshTouchStateRef.current.isTracking || event.touches.length !== 1) {
        return;
      }
      if (getVerticalScrollOffset() > 0) {
        resetGestureState();
        return;
      }

      const currentY = event.touches[0]?.clientY ?? pullToRefreshTouchStateRef.current.startY;
      const offset = getPullToRefreshOffset(currentY - pullToRefreshTouchStateRef.current.startY);
      if (offset <= 0) {
        setPullToRefreshOffset(0);
        setPullToRefreshPhase("idle");
        pullToRefreshTouchStateRef.current.lastOffset = 0;
        return;
      }

      event.preventDefault();
      pullToRefreshTouchStateRef.current.lastOffset = offset;
      setPullToRefreshOffset(offset);
      setPullToRefreshPhase(offset >= PULL_TO_REFRESH_THRESHOLD ? "armed" : "pulling");
    }

    function handleTouchEnd() {
      const { lastOffset, isTracking } = pullToRefreshTouchStateRef.current;
      if (!isTracking) {
        return;
      }

      pullToRefreshTouchStateRef.current.isTracking = false;
      pullToRefreshTouchStateRef.current.startY = 0;
      pullToRefreshTouchStateRef.current.lastOffset = 0;

      if (
        lastOffset >= PULL_TO_REFRESH_THRESHOLD &&
        !isBootstrapping &&
        !isBrowserOffline &&
        session.accessToken
      ) {
        void refreshDashboardFromPull(session.accessToken);
        return;
      }

      setPullToRefreshOffset(0);
      setPullToRefreshPhase("idle");
    }

    window.addEventListener("touchstart", handleTouchStart, { passive: true });
    window.addEventListener("touchmove", handleTouchMove, { passive: false });
    window.addEventListener("touchend", handleTouchEnd);
    window.addEventListener("touchcancel", handleTouchEnd);
    return () => {
      window.removeEventListener("touchstart", handleTouchStart);
      window.removeEventListener("touchmove", handleTouchMove);
      window.removeEventListener("touchend", handleTouchEnd);
      window.removeEventListener("touchcancel", handleTouchEnd);
      pullToRefreshTouchStateRef.current.isTracking = false;
      pullToRefreshTouchStateRef.current.startY = 0;
      pullToRefreshTouchStateRef.current.lastOffset = 0;
    };
  }, [
    isBootstrapping,
    isBrowserOffline,
    isManualSearchOpen,
    isSettingsOpen,
    session.accessToken,
    session.isAuthenticated,
  ]);

  useEffect(() => {
    const serviceWorker = "serviceWorker" in navigator ? navigator.serviceWorker : undefined;
    const accessToken = session.accessToken;
    if (
      !serviceWorker ||
      typeof serviceWorker.addEventListener !== "function" ||
      typeof serviceWorker.removeEventListener !== "function" ||
      !accessToken
    ) {
      pendingPushRefreshTargetsRef.current.clear();
      if (pushRefreshTimeoutRef.current !== null) {
        window.clearTimeout(pushRefreshTimeoutRef.current);
        pushRefreshTimeoutRef.current = null;
      }
      return;
    }

    function flushPushRefreshQueue() {
      const queuedTargets = Array.from(pendingPushRefreshTargetsRef.current);
      pendingPushRefreshTargetsRef.current.clear();
      pushRefreshTimeoutRef.current = null;

      if (queuedTargets.length === 0 || isBrowserOffline) {
        return;
      }

      void refreshResources(accessToken, queuedTargets, {
        silent: true,
        allowTabAttention: true,
      });
    }

    function schedulePushRefresh(targets: PushRefreshTarget[]) {
      targets.forEach((target) => pendingPushRefreshTargetsRef.current.add(target));
      if (pushRefreshTimeoutRef.current !== null) {
        return;
      }
      pushRefreshTimeoutRef.current = window.setTimeout(flushPushRefreshQueue, 350);
    }

    function handleServiceWorkerMessage(event: MessageEvent) {
      const data = event.data as { type?: string; payload?: { refresh_targets?: unknown } } | null;
      if (data?.type !== PUSH_MESSAGE_TYPE) {
        return;
      }

      const targets = normalizePushRefreshTargets(data.payload?.refresh_targets);
      if (targets.length === 0) {
        return;
      }

      schedulePushRefresh(targets);
    }

    serviceWorker.addEventListener("message", handleServiceWorkerMessage);
    return () => {
      serviceWorker.removeEventListener("message", handleServiceWorkerMessage);
      if (pushRefreshTimeoutRef.current !== null) {
        window.clearTimeout(pushRefreshTimeoutRef.current);
        pushRefreshTimeoutRef.current = null;
      }
      pendingPushRefreshTargetsRef.current.clear();
    };
  }, [isBrowserOffline, session.accessToken]);

  useEffect(() => {
    if (!session.accessToken || !isSettingsOpen) {
      return;
    }
    const tasks = [loadPushSubscriptionsResource(session.accessToken)];
    if (isAdmin) {
      tasks.push(loadPushConfigResource(session.accessToken), detectCurrentPushSubscriptionEndpoint());
    }
    void Promise.allSettled(tasks);
  }, [isAdmin, isSettingsOpen, session.accessToken]);

  async function refreshLiveSyncStatus(token: string): Promise<LiveSyncStatus | null> {
    try {
      const status = await getSystemStatus(token);
      setLiveSyncStatus(status.live_sync);
      setDashboardErrorState("liveSync", null);
      return status.live_sync;
    } catch (caught) {
      setDashboardErrorState("liveSync", toErrorMessage(caught, "Could not load live-sync status."));
      return null;
    }
  }

  function isLiveSyncUnavailable(status: LiveSyncStatus | null): boolean {
    return status?.status === "degraded";
  }

  function formatConnectivityError(actionLabel: string, fallbackMessage: string, status: LiveSyncStatus | null): string {
    if (isBrowserOffline) {
      return `${actionLabel} is unavailable because this device is offline. Reconnect and try again.`;
    }
    if (isLiveSyncUnavailable(status)) {
      return `${actionLabel} is unavailable right now because live Copart sync is offline. Cached data remains available.`;
    }
    return fallbackMessage;
  }

  async function refreshConnectorAwareResources(token: string) {
    await Promise.allSettled([loadProviderConnectionsResource(token), loadSavedSearchesResource(token), loadWatchlistResource(token)]);
  }

  async function handleLogin(email: string, password: string) {
    try {
      setGlobalError(null);
      const result = await login(email, password);
      session.persist(result.user, result.tokens);
      navigate("/dashboard");
    } catch (caught) {
      setGlobalError(toErrorMessage(caught, "Login failed"));
    }
  }

  async function handleInviteAccept(password: string) {
    const inviteToken = routeState.params.get("token") ?? "";
    try {
      setGlobalError(null);
      await acceptInvite(inviteToken, password);
      navigate("/login");
    } catch (caught) {
      setGlobalError(toErrorMessage(caught, "Invite activation failed"));
    }
  }

  function mergeSavedSearch(savedSearch: SavedSearch) {
    setSavedSearches((current) => [savedSearch, ...current.filter((item) => item.id !== savedSearch.id)]);
  }

  async function handleSearch(payload: SearchPayload): Promise<{ results: SearchResult[]; total_results: number }> {
    if (!session.accessToken) {
      throw new Error("Missing session");
    }
    setActionState((current) => ({ ...current, isSearching: true }));
    try {
      const response = await searchLots(
        {
          make: payload.make,
          model: payload.model,
          make_filter: payload.makeFilter,
          model_filter: payload.modelFilter,
          drive_type: payload.driveType,
          primary_damage: payload.primaryDamage,
          title_type: payload.titleType,
          fuel_type: payload.fuelType,
          lot_condition: payload.lotCondition,
          odometer_range: payload.odometerRange,
          year_from: payload.yearFrom ? Number(payload.yearFrom) : undefined,
          year_to: payload.yearTo ? Number(payload.yearTo) : undefined,
        },
        session.accessToken,
      );
      await refreshLiveSyncStatus(session.accessToken);
      setSearchResults(response.results);
      setSearchTotalResults(response.total_results);
      return response;
    } catch (caught) {
      const status = isBrowserOffline ? liveSyncStatus : await refreshLiveSyncStatus(session.accessToken);
      const message = formatConnectivityError("Search", toErrorMessage(caught, "Search failed"), status);
      throw new Error(message);
    } finally {
      setActionState((current) => ({ ...current, isSearching: false }));
    }
  }

  async function handleSaveSearch(
    payload: SearchPayload & { seedResults?: SearchResult[]; totalResults?: number },
  ): Promise<SavedSearch> {
    if (!session.accessToken) {
      throw new Error("Missing session");
    }
    setActionState((current) => ({ ...current, isSavingSearch: true }));
    try {
      const saved = await saveSearch(
        {
          make: payload.make,
          model: payload.model,
          make_filter: payload.makeFilter,
          model_filter: payload.modelFilter,
          drive_type: payload.driveType,
          primary_damage: payload.primaryDamage,
          title_type: payload.titleType,
          fuel_type: payload.fuelType,
          lot_condition: payload.lotCondition,
          odometer_range: payload.odometerRange,
          year_from: payload.yearFrom ? Number(payload.yearFrom) : undefined,
          year_to: payload.yearTo ? Number(payload.yearTo) : undefined,
          result_count: payload.totalResults ?? searchTotalResults,
          seed_results: payload.seedResults ?? searchResults,
        },
        session.accessToken,
      );
      mergeSavedSearch(saved);
      return saved;
    } catch (caught) {
      throw new Error(toErrorMessage(caught, "Could not save search"));
    } finally {
      setActionState((current) => ({ ...current, isSavingSearch: false }));
    }
  }

  async function handleViewSavedSearch(id: string): Promise<SavedSearchResultsResponse> {
    if (!session.accessToken) {
      throw new Error("Missing session");
    }
    setActionState((current) => ({ ...current, openingSavedSearchId: id }));
    try {
      const response = await viewSavedSearch(id, session.accessToken);
      mergeSavedSearch(response.saved_search);
      return response;
    } catch (caught) {
      throw new Error(toErrorMessage(caught, "Could not open saved search"));
    } finally {
      setActionState((current) =>
        current.openingSavedSearchId === id ? { ...current, openingSavedSearchId: null } : current,
      );
    }
  }

  async function handleRefreshSavedSearch(id: string): Promise<SavedSearchResultsResponse> {
    if (!session.accessToken) {
      throw new Error("Missing session");
    }
    setActionState((current) => ({ ...current, refreshingSavedSearchId: id }));
    try {
      const response = await refreshSavedSearchLive(id, session.accessToken);
      await refreshLiveSyncStatus(session.accessToken);
      mergeSavedSearch(response.saved_search);
      return response;
    } catch (caught) {
      const status = isBrowserOffline ? liveSyncStatus : await refreshLiveSyncStatus(session.accessToken);
      await loadSavedSearchesResource(session.accessToken, { silent: true });
      const message = formatConnectivityError(
        "Saved-search refresh",
        toErrorMessage(caught, "Could not refresh saved search"),
        status,
      );
      throw new Error(message);
    } finally {
      setActionState((current) =>
        current.refreshingSavedSearchId === id ? { ...current, refreshingSavedSearchId: null } : current,
      );
    }
  }

  async function handleRefreshWatchlistLot(id: string): Promise<WatchlistItem> {
    if (!session.accessToken) {
      throw new Error("Missing session");
    }
    setActionState((current) => ({ ...current, refreshingWatchlistId: id }));
    try {
      const trackedLot = await refreshWatchlistLotLive(id, session.accessToken);
      await refreshLiveSyncStatus(session.accessToken);
      setWatchlist((current) => sortWatchlistItems([trackedLot, ...current.filter((item) => item.id !== trackedLot.id)]));
      return trackedLot;
    } catch (caught) {
      const status = isBrowserOffline ? liveSyncStatus : await refreshLiveSyncStatus(session.accessToken);
      await loadWatchlistResource(session.accessToken, { silent: true });
      throw new Error(
        formatConnectivityError(
          "Watchlist refresh",
          toErrorMessage(caught, "Could not refresh tracked lot"),
          status,
        ),
      );
    } finally {
      setActionState((current) =>
        current.refreshingWatchlistId === id ? { ...current, refreshingWatchlistId: null } : current,
      );
    }
  }

  async function handleAddFromSearch(lotUrl: string) {
    if (!session.accessToken) {
      throw new Error("Missing session");
    }
    setActionState((current) => ({ ...current, addingFromSearchLotUrl: lotUrl }));
    try {
      const trackedLot = await addFromSearch(lotUrl, session.accessToken);
      await refreshLiveSyncStatus(session.accessToken);
      setWatchlist((current) => sortWatchlistItems([trackedLot, ...current.filter((item) => item.id !== trackedLot.id)]));
      return trackedLot;
    } catch (caught) {
      const status = isBrowserOffline ? liveSyncStatus : await refreshLiveSyncStatus(session.accessToken);
      throw new Error(
        formatConnectivityError(
          "Adding a lot from search",
          toErrorMessage(caught, "Could not add lot"),
          status,
        ),
      );
    } finally {
      setActionState((current) =>
        current.addingFromSearchLotUrl === lotUrl ? { ...current, addingFromSearchLotUrl: null } : current,
      );
    }
  }

  async function handleDeleteSavedSearch(id: string) {
    if (!session.accessToken) {
      throw new Error("Missing session");
    }
    setActionState((current) => ({ ...current, deletingSavedSearchId: id }));
    try {
      await deleteSavedSearch(id, session.accessToken);
      setSavedSearches((current) => current.filter((item) => item.id !== id));
    } catch (caught) {
      throw new Error(toErrorMessage(caught, "Could not delete saved search"));
    } finally {
      setActionState((current) =>
        current.deletingSavedSearchId === id ? { ...current, deletingSavedSearchId: null } : current,
      );
    }
  }

  async function handleRemoveWatchlistItem(id: string) {
    if (!session.accessToken) {
      throw new Error("Missing session");
    }
    setActionState((current) => ({ ...current, removingWatchlistId: id }));
    try {
      await removeWatchlistItem(id, session.accessToken);
      setWatchlist((current) => current.filter((item) => item.id !== id));
    } catch (caught) {
      throw new Error(toErrorMessage(caught, "Could not remove lot"));
    } finally {
      setActionState((current) =>
        current.removingWatchlistId === id ? { ...current, removingWatchlistId: null } : current,
      );
    }
  }

  async function handleAddByLotNumber(lotNumber: string) {
    if (!session.accessToken) {
      throw new Error("Missing session");
    }
    setActionState((current) => ({ ...current, isAddingWatchlistLot: true }));
    try {
      const trackedLot = await addLotNumberToWatchlist(lotNumber, session.accessToken);
      await refreshLiveSyncStatus(session.accessToken);
      setWatchlist((current) => sortWatchlistItems([trackedLot, ...current.filter((item) => item.id !== trackedLot.id)]));
      return trackedLot;
    } catch (caught) {
      const status = isBrowserOffline ? liveSyncStatus : await refreshLiveSyncStatus(session.accessToken);
      throw new Error(
        formatConnectivityError(
          "Adding a lot to the watchlist",
          toErrorMessage(caught, "Could not add lot"),
          status,
        ),
      );
    } finally {
      setActionState((current) => ({ ...current, isAddingWatchlistLot: false }));
    }
  }

  async function handleCreateInvite(email: string): Promise<Invite> {
    if (!session.accessToken) {
      throw new Error("Missing session");
    }
    setActionState((current) => ({ ...current, isCreatingInvite: true }));
    try {
      const invite = await createInvite(email, session.accessToken);
      setLatestInvite(invite);
      setInviteLink(`${window.location.origin}${window.location.pathname}#/invite?token=${invite.token}`);
      return invite;
    } catch (caught) {
      throw new Error(toErrorMessage(caught, "Could not create invite"));
    } finally {
      setActionState((current) => ({ ...current, isCreatingInvite: false }));
    }
  }

  async function handleRefreshSearchCatalog() {
    if (!session.accessToken) {
      throw new Error("Missing session");
    }
    setActionState((current) => ({ ...current, isRefreshingCatalog: true }));
    try {
      const refreshedCatalog = await refreshSearchCatalog(session.accessToken);
      await refreshLiveSyncStatus(session.accessToken);
      setSearchCatalog(refreshedCatalog);
      setDashboardErrorState("searchCatalog", null);
      return refreshedCatalog;
    } catch (caught) {
      const status = isBrowserOffline ? liveSyncStatus : await refreshLiveSyncStatus(session.accessToken);
      throw new Error(
        formatConnectivityError(
          "Refreshing the search catalog",
          toErrorMessage(caught, "Could not refresh search catalog"),
          status,
        ),
      );
    } finally {
      setActionState((current) => ({ ...current, isRefreshingCatalog: false }));
    }
  }

  async function handleConnectCopart(payload: { username: string; password: string }) {
    if (!session.accessToken) {
      throw new Error("Missing session");
    }
    await connectCopartConnection(payload, session.accessToken);
    await refreshConnectorAwareResources(session.accessToken);
  }

  async function handleReconnectCopart(payload: { username: string; password: string }) {
    if (!session.accessToken) {
      throw new Error("Missing session");
    }
    await reconnectCopartConnection(payload, session.accessToken);
    await refreshConnectorAwareResources(session.accessToken);
  }

  async function handleDisconnectCopart() {
    if (!session.accessToken) {
      throw new Error("Missing session");
    }
    await disconnectCopartConnection(session.accessToken);
    await refreshConnectorAwareResources(session.accessToken);
  }

  async function handleSubscribePush() {
    if (!session.accessToken) {
      throw new Error("Missing session");
    }
    setActionState((current) => ({ ...current, isSubscribingPush: true }));
    try {
      if (isBrowserOffline) {
        throw new Error("Push setup is unavailable because this device is offline. Reconnect and try again.");
      }
      if (!isSecurePushContext) {
        throw new Error("Push notifications require HTTPS or localhost.");
      }
      if (typeof Notification === "undefined" || !("PushManager" in window)) {
        setPermissionState("unsupported");
        throw new Error("This browser does not support push notifications.");
      }

      const permission = Notification.permission === "granted" ? "granted" : await Notification.requestPermission();
      setPermissionState(permission);
      if (permission !== "granted") {
        throw new Error(
          permission === "denied"
            ? "Browser notifications are blocked for this site."
            : "Notification permission request was dismissed.",
        );
      }

      const config = pushConfig ?? (await loadPushConfigResource(session.accessToken));
      if (!config?.enabled || !config.public_key) {
        throw new Error(config?.reason ?? "Push notifications are not configured on the server.");
      }

      const registration = await ensurePushRegistration();
      const existingSubscription = await registration.pushManager.getSubscription();
      const browserSubscription =
        existingSubscription ??
        (await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: decodeBase64Url(config.public_key),
        }));
      const created = await subscribeToPush(
        serializePushSubscription(browserSubscription),
        navigator.userAgent,
        session.accessToken,
      );
      setSubscriptions((current) => [created, ...current.filter((item) => item.endpoint !== created.endpoint)]);
      setCurrentPushEndpoint(created.endpoint);
      return created;
    } catch (caught) {
      throw new Error(toErrorMessage(caught, "Could not enable push notifications"));
    } finally {
      setActionState((current) => ({ ...current, isSubscribingPush: false }));
    }
  }

  async function handleUnsubscribePush(endpoint: string) {
    if (!session.accessToken) {
      throw new Error("Missing session");
    }
    setActionState((current) => ({ ...current, unsubscribingEndpoint: endpoint }));
    try {
      if ("serviceWorker" in navigator) {
        const registration = await navigator.serviceWorker.getRegistration();
        const browserSubscription = await registration?.pushManager.getSubscription();
        if (browserSubscription?.endpoint === endpoint) {
          await browserSubscription.unsubscribe();
        }
      }
      await unsubscribeFromPush(endpoint, session.accessToken);
      setSubscriptions((current) => current.filter((item) => item.endpoint !== endpoint));
      if (currentPushEndpoint === endpoint) {
        setCurrentPushEndpoint(null);
      }
    } catch (caught) {
      throw new Error(toErrorMessage(caught, "Could not revoke push subscription"));
    } finally {
      setActionState((current) =>
        current.unsubscribingEndpoint === endpoint ? { ...current, unsubscribingEndpoint: null } : current,
      );
    }
  }

  async function handleSendPushTest(): Promise<PushDeliveryResult> {
    if (!session.accessToken) {
      throw new Error("Missing session");
    }
    if (!isAdmin) {
      throw new Error("Push diagnostics are available only for admin accounts.");
    }
    setActionState((current) => ({ ...current, isSendingPushTest: true }));
    try {
      if (isBrowserOffline) {
        throw new Error("Push diagnostics are unavailable because this device is offline. Reconnect and try again.");
      }
      return await sendPushTest(session.accessToken);
    } catch (caught) {
      throw new Error(toErrorMessage(caught, "Could not send test push"));
    } finally {
      setActionState((current) => ({ ...current, isSendingPushTest: false }));
    }
  }

  function handleOpenSettings() {
    setIsAccountMenuOpen(false);
    setIsSettingsOpen(true);
  }

  function handleLogout() {
    session.logout();
    resetDashboardData();
    setGlobalError(null);
    setIsSettingsOpen(false);
    navigate("/login");
  }

  if (routeState.route === "invite") {
    return (
      <InviteAcceptScreen
        inviteToken={routeState.params.get("token") ?? ""}
        error={globalError}
        onSubmit={handleInviteAccept}
      />
    );
  }

  if (!session.isAuthenticated) {
    return <LoginScreen error={globalError} onSubmit={handleLogin} />;
  }

  return (
    <>
      <DashboardShell
        isBrowserOffline={isBrowserOffline}
        isBootstrapping={isBootstrapping}
        isPullToRefreshEnabled={isMobilePullToRefreshEnabled}
        pullToRefreshPhase={pullToRefreshPhase}
        pullToRefreshStyle={pullToRefreshStyle}
        isAccountMenuOpen={isAccountMenuOpen}
        onToggleAccountMenu={() => setIsAccountMenuOpen((current) => !current)}
      >
        {globalError ? (
          <AsyncStatus
            tone="error"
            title="Session issue"
            message={globalError}
            className="dashboard-status dashboard-grid__status"
          />
        ) : null}
        {copartConnection?.status === "reconnect_required" ? (
          <AsyncStatus
            tone="neutral"
            title="Copart reconnect required"
            message="Live search and refresh actions are blocked until you reconnect Copart from Account."
            className="dashboard-status dashboard-grid__status"
          />
        ) : null}
        <SearchPanel
          catalog={searchCatalog}
          isLoadingCatalog={dashboardLoading.searchCatalog}
          catalogError={dashboardErrors.searchCatalog}
          onRetryCatalog={() => (session.accessToken ? loadSearchCatalogResource(session.accessToken) : Promise.resolve())}
          savedSearches={savedSearches}
          isLoadingSavedSearches={dashboardLoading.savedSearches}
          savedSearchesError={dashboardErrors.savedSearches}
          onRetrySavedSearches={() =>
            session.accessToken ? loadSavedSearchesResource(session.accessToken) : Promise.resolve()
          }
          copartConnectionDiagnostic={copartConnectionDiagnostic}
          isSearching={actionState.isSearching}
          isSavingSearch={actionState.isSavingSearch}
          openingSavedSearchId={actionState.openingSavedSearchId}
          refreshingSavedSearchId={actionState.refreshingSavedSearchId}
          deletingSavedSearchId={actionState.deletingSavedSearchId}
          addingFromSearchLotUrl={actionState.addingFromSearchLotUrl}
          trackedLotUrls={watchlist.map((item) => item.url)}
          isBrowserOffline={isBrowserOffline}
          liveSyncStatus={liveSyncStatus}
          isManualSearchOpen={isManualSearchOpen}
          onOpenManualSearch={() => setIsManualSearchOpen(true)}
          onCloseManualSearch={() => setIsManualSearchOpen(false)}
          onSearch={handleSearch}
          onSaveSearch={handleSaveSearch}
          onViewSavedSearch={handleViewSavedSearch}
          onRefreshSavedSearch={handleRefreshSavedSearch}
          onDeleteSavedSearch={handleDeleteSavedSearch}
          onAddFromSearch={handleAddFromSearch}
        />
        <WatchlistPanel
          items={watchlist}
          isLoading={dashboardLoading.watchlist}
          loadError={dashboardErrors.watchlist}
          isAddingLot={actionState.isAddingWatchlistLot}
          refreshingItemId={actionState.refreshingWatchlistId}
          removingItemId={actionState.removingWatchlistId}
          isBrowserOffline={isBrowserOffline}
          liveSyncStatus={liveSyncStatus}
          copartConnectionDiagnostic={copartConnectionDiagnostic}
          onRetry={() => (session.accessToken ? loadWatchlistResource(session.accessToken) : Promise.resolve())}
          onAddByLotNumber={handleAddByLotNumber}
          onRefreshItem={handleRefreshWatchlistLot}
          onRemove={handleRemoveWatchlistItem}
        />
        {isAdmin ? (
          <div className="dashboard-grid__support" aria-label="Support panels">
            <AdminInvitesPanel
              inviteLink={inviteLink}
              latestInvite={latestInvite}
              isCreatingInvite={actionState.isCreatingInvite}
              onCreateInvite={handleCreateInvite}
            />
            <AdminSearchCatalogPanel
              catalog={searchCatalog}
              loadError={dashboardErrors.searchCatalog}
              isLoading={dashboardLoading.searchCatalog}
              isRefreshing={actionState.isRefreshingCatalog}
              onRefresh={handleRefreshSearchCatalog}
              onRetryLoad={() => (session.accessToken ? loadSearchCatalogResource(session.accessToken) : Promise.resolve())}
            />
          </div>
        ) : null}
      </DashboardShell>
      <AccountMenuSheet
        isOpen={isAccountMenuOpen}
        user={session.user!}
        liveSyncStatus={liveSyncStatus}
        diagnostics={reliabilityDiagnostics}
        copartConnection={copartConnection}
        copartConnectionError={providerConnectionsError}
        isLoadingCopartConnection={isLoadingProviderConnections}
        isBrowserOffline={isBrowserOffline}
        onConnectCopart={handleConnectCopart}
        onReconnectCopart={handleReconnectCopart}
        onDisconnectCopart={handleDisconnectCopart}
        onClose={() => setIsAccountMenuOpen(false)}
        onOpenSettings={handleOpenSettings}
        onLogout={handleLogout}
      />
      <PushSettingsModal
        isOpen={isSettingsOpen}
        isAdmin={isAdmin}
        subscriptions={subscriptions}
        subscriptionsError={dashboardErrors.subscriptions}
        isLoadingSubscriptions={dashboardLoading.subscriptions}
        pushConfig={pushConfig}
        pushConfigError={pushConfigError}
        isLoadingPushConfig={isLoadingPushConfig}
        currentDeviceEndpoint={currentPushEndpoint}
        permissionState={permissionState}
        supportsPush={supportsPush}
        isSecureContext={isSecurePushContext}
        isBrowserOffline={isBrowserOffline}
        isSubscribing={actionState.isSubscribingPush}
        unsubscribingEndpoint={actionState.unsubscribingEndpoint}
        isSendingTestPush={actionState.isSendingPushTest}
        onRetryDiagnostics={() =>
          session.accessToken && isAdmin
            ? Promise.allSettled([
                loadPushSubscriptionsResource(session.accessToken),
                loadPushConfigResource(session.accessToken),
                detectCurrentPushSubscriptionEndpoint(),
              ]).then(() => undefined)
            : session.accessToken
              ? loadPushSubscriptionsResource(session.accessToken)
              : Promise.resolve()
        }
        onSubscribe={handleSubscribePush}
        onUnsubscribe={handleUnsubscribePush}
        onSendTestPush={handleSendPushTest}
        onClose={() => setIsSettingsOpen(false)}
      />
    </>
  );
}
