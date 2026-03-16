import { useEffect, useState } from "react";

import { DashboardShell } from "./features/dashboard/DashboardShell";
import { AdminInvitesPanel } from "./features/admin/AdminInvitesPanel";
import { AdminSearchCatalogPanel } from "./features/admin/AdminSearchCatalogPanel";
import { InviteAcceptScreen } from "./features/auth/InviteAcceptScreen";
import { LoginScreen } from "./features/auth/LoginScreen";
import { PushSettingsModal } from "./features/push/PushSettingsModal";
import { SearchPanel } from "./features/search/SearchPanel";
import { WatchlistPanel } from "./features/watchlist/WatchlistPanel";
import { useHashRoute } from "./app/router";
import { useSession } from "./app/useSession";
import {
  acceptInvite,
  addFromSearch,
  addLotNumberToWatchlist,
  configureAuthLifecycle,
  createInvite,
  deleteSavedSearch,
  getSearchCatalog,
  getPushSubscriptionConfig,
  getSystemStatus,
  listPushSubscriptions,
  listSavedSearches,
  listWatchlist,
  login,
  removeWatchlistItem,
  refreshSavedSearchLive,
  refreshSearchCatalog,
  saveSearch,
  searchLots,
  subscribeToPush,
  unsubscribeFromPush,
  viewSavedSearch,
} from "./lib/api";
import type {
  Invite,
  LiveSyncStatus,
  PushSubscriptionItem,
  PushSubscriptionPayload,
  SavedSearch,
  SearchCatalog,
  SearchResult,
  SavedSearchResultsResponse,
  WatchlistItem,
} from "./types";

function getNotificationPermission(): string {
  return typeof Notification === "undefined" ? "unsupported" : Notification.permission;
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
  const [error, setError] = useState<string | null>(null);
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searchTotalResults, setSearchTotalResults] = useState(0);
  const [savedSearches, setSavedSearches] = useState<SavedSearch[]>([]);
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [inviteLink, setInviteLink] = useState<string | null>(null);
  const [subscriptions, setSubscriptions] = useState<PushSubscriptionItem[]>([]);
  const [searchCatalog, setSearchCatalog] = useState<SearchCatalog | null>(null);
  const [isLoadingSearchCatalog, setIsLoadingSearchCatalog] = useState(false);
  const [permissionState, setPermissionState] = useState(getNotificationPermission());
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [liveSyncStatus, setLiveSyncStatus] = useState<LiveSyncStatus | null>(null);

  useEffect(() => {
    if (!window.location.hash) {
      window.location.hash = "#/login";
    }
  }, []);

  useEffect(() => {
    configureAuthLifecycle({
      onTokensRefreshed: session.updateTokens,
      onAuthFailed: () => {
        session.logout();
        setSearchResults([]);
        setSearchTotalResults(0);
        setSavedSearches([]);
        setWatchlist([]);
        setSubscriptions([]);
        setSearchCatalog(null);
        setLiveSyncStatus(null);
        setError("Session expired. Please sign in again.");
        navigate("/login");
      },
    });
  }, [navigate, session]);

  useEffect(() => {
    if (!session.accessToken) {
      return;
    }
    setIsLoadingSearchCatalog(true);
    void Promise.allSettled([
      listWatchlist(session.accessToken),
      listSavedSearches(session.accessToken),
      listPushSubscriptions(session.accessToken),
      getSearchCatalog(session.accessToken),
      getSystemStatus(session.accessToken),
    ]).then((results) => {
      const [watchlistResult, savedSearchesResult, pushResult, catalogResult, systemStatusResult] = results;
      if (watchlistResult.status === "fulfilled") {
        setWatchlist(watchlistResult.value);
      }
      if (savedSearchesResult.status === "fulfilled") {
        setSavedSearches(savedSearchesResult.value);
      }
      if (pushResult.status === "fulfilled") {
        setSubscriptions(pushResult.value);
      }
      if (catalogResult.status === "fulfilled") {
        setSearchCatalog(catalogResult.value);
      }
      if (systemStatusResult.status === "fulfilled") {
        setLiveSyncStatus(systemStatusResult.value.live_sync);
      }
      setIsLoadingSearchCatalog(false);
    });
  }, [session.accessToken]);

  async function refreshLiveSyncStatus(token: string): Promise<LiveSyncStatus | null> {
    try {
      const status = await getSystemStatus(token);
      setLiveSyncStatus(status.live_sync);
      return status.live_sync;
    } catch {
      return null;
    }
  }

  function isLiveSyncUnavailable(status: LiveSyncStatus | null): boolean {
    return status?.status === "degraded";
  }

  function formatLiveSyncActionError(actionLabel: string, fallbackMessage: string, status: LiveSyncStatus | null): string {
    if (!isLiveSyncUnavailable(status)) {
      return fallbackMessage;
    }
    return `${actionLabel} is unavailable right now because live Copart sync is offline. Cached data remains available.`;
  }

  async function handleLogin(email: string, password: string) {
    try {
      setError(null);
      const result = await login(email, password);
      session.persist(result.user, result.tokens);
      navigate("/dashboard");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Login failed");
    }
  }

  async function handleInviteAccept(password: string) {
    const inviteToken = routeState.params.get("token") ?? "";
    try {
      setError(null);
      await acceptInvite(inviteToken, password);
      navigate("/login");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Invite activation failed");
    }
  }

  function mergeSavedSearch(savedSearch: SavedSearch) {
    setSavedSearches((current) => [savedSearch, ...current.filter((item) => item.id !== savedSearch.id)]);
  }

  async function handleSearch(payload: {
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
  }): Promise<{ results: SearchResult[]; total_results: number }> {
    if (!session.accessToken) {
      throw new Error("Missing session");
    }
    try {
      setError(null);
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
      const status = await refreshLiveSyncStatus(session.accessToken);
      const fallbackMessage = caught instanceof Error ? caught.message : "Search failed";
      const message = formatLiveSyncActionError("Search", fallbackMessage, status);
      setError(message);
      throw new Error(message);
    }
  }

  async function handleSaveSearch(payload: {
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
    seedResults?: SearchResult[];
    totalResults?: number;
  }): Promise<SavedSearch> {
    if (!session.accessToken) {
      throw new Error("Missing session");
    }
    try {
      setError(null);
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
      const message = caught instanceof Error ? caught.message : "Could not save search";
      setError(message);
      throw new Error(message);
    }
  }

  async function handleViewSavedSearch(id: string): Promise<SavedSearchResultsResponse> {
    if (!session.accessToken) {
      throw new Error("Missing session");
    }
    try {
      setError(null);
      const response = await viewSavedSearch(id, session.accessToken);
      mergeSavedSearch(response.saved_search);
      return response;
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : "Could not open saved search";
      setError(message);
      throw new Error(message);
    }
  }

  async function handleRefreshSavedSearch(id: string): Promise<SavedSearchResultsResponse> {
    if (!session.accessToken) {
      throw new Error("Missing session");
    }
    try {
      setError(null);
      const response = await refreshSavedSearchLive(id, session.accessToken);
      await refreshLiveSyncStatus(session.accessToken);
      mergeSavedSearch(response.saved_search);
      return response;
    } catch (caught) {
      const status = await refreshLiveSyncStatus(session.accessToken);
      const fallbackMessage = caught instanceof Error ? caught.message : "Could not refresh saved search";
      const message = formatLiveSyncActionError("Saved-search refresh", fallbackMessage, status);
      setError(message);
      throw new Error(message);
    }
  }

  async function handleAddFromSearch(lotUrl: string) {
    if (!session.accessToken) return;
    try {
      const trackedLot = await addFromSearch(lotUrl, session.accessToken);
      await refreshLiveSyncStatus(session.accessToken);
      setWatchlist((current) => [trackedLot, ...current.filter((item) => item.id !== trackedLot.id)]);
    } catch (caught) {
      const status = await refreshLiveSyncStatus(session.accessToken);
      setError(
        formatLiveSyncActionError(
          "Adding a lot from search",
          caught instanceof Error ? caught.message : "Could not add lot",
          status,
        ),
      );
    }
  }

  async function handleDeleteSavedSearch(id: string) {
    if (!session.accessToken) {
      return;
    }
    try {
      setError(null);
      await deleteSavedSearch(id, session.accessToken);
      setSavedSearches((current) => current.filter((item) => item.id !== id));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not delete saved search");
    }
  }

  async function handleRemoveWatchlistItem(id: string) {
    if (!session.accessToken) return;
    await removeWatchlistItem(id, session.accessToken);
    setWatchlist((current) => current.filter((item) => item.id !== id));
  }

  async function handleAddByLotNumber(lotNumber: string) {
    if (!session.accessToken) return;
    try {
      setError(null);
      const trackedLot = await addLotNumberToWatchlist(lotNumber, session.accessToken);
      await refreshLiveSyncStatus(session.accessToken);
      setWatchlist((current) => [trackedLot, ...current.filter((item) => item.id !== trackedLot.id)]);
    } catch (caught) {
      const status = await refreshLiveSyncStatus(session.accessToken);
      setError(
        formatLiveSyncActionError(
          "Adding a lot to the watchlist",
          caught instanceof Error ? caught.message : "Could not add lot",
          status,
        ),
      );
    }
  }

  async function handleCreateInvite(email: string): Promise<Invite> {
    if (!session.accessToken) {
      throw new Error("Missing session");
    }
    const invite = await createInvite(email, session.accessToken);
    setInviteLink(`${window.location.origin}${window.location.pathname}#/invite?token=${invite.token}`);
    return invite;
  }

  async function handleRefreshSearchCatalog() {
    if (!session.accessToken) {
      return;
    }
    try {
      setError(null);
      const refreshedCatalog = await refreshSearchCatalog(session.accessToken);
      await refreshLiveSyncStatus(session.accessToken);
      setSearchCatalog(refreshedCatalog);
    } catch (caught) {
      const status = await refreshLiveSyncStatus(session.accessToken);
      setError(
        formatLiveSyncActionError(
          "Refreshing the search catalog",
          caught instanceof Error ? caught.message : "Could not refresh search catalog",
          status,
        ),
      );
    }
  }

  async function handleSubscribePush() {
    if (!session.accessToken) return;
    try {
      setError(null);
      if (!window.isSecureContext) {
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

      const config = await getPushSubscriptionConfig(session.accessToken);
      if (!config.enabled || !config.public_key) {
        throw new Error(config.reason ?? "Push notifications are not configured on the server.");
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
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not enable push notifications");
    }
  }

  async function handleUnsubscribePush(endpoint: string) {
    if (!session.accessToken) return;
    try {
      setError(null);
      if ("serviceWorker" in navigator) {
        const registration = await navigator.serviceWorker.getRegistration();
        const browserSubscription = await registration?.pushManager.getSubscription();
        if (browserSubscription?.endpoint === endpoint) {
          await browserSubscription.unsubscribe();
        }
      }
      await unsubscribeFromPush(endpoint, session.accessToken);
      setSubscriptions((current) => current.filter((item) => item.endpoint !== endpoint));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not revoke push subscription");
    }
  }

  function handleLogout() {
    session.logout();
    setSearchResults([]);
    setSearchTotalResults(0);
    setSavedSearches([]);
    setWatchlist([]);
    setSubscriptions([]);
    setSearchCatalog(null);
    setLiveSyncStatus(null);
    setIsSettingsOpen(false);
    navigate("/login");
  }

  if (routeState.route === "invite") {
    return (
      <InviteAcceptScreen
        inviteToken={routeState.params.get("token") ?? ""}
        error={error}
        onSubmit={handleInviteAccept}
      />
    );
  }

  if (!session.isAuthenticated) {
    return <LoginScreen error={error} onSubmit={handleLogin} />;
  }

  return (
    <>
      <DashboardShell
        user={session.user!}
        liveSyncStatus={liveSyncStatus}
        onLogout={handleLogout}
        onOpenSettings={() => setIsSettingsOpen(true)}
      >
        {error ? <p className="error">{error}</p> : null}
        {session.user?.role === "admin" ? (
          <>
            <AdminInvitesPanel inviteLink={inviteLink} onCreateInvite={handleCreateInvite} />
            <AdminSearchCatalogPanel catalog={searchCatalog} onRefresh={handleRefreshSearchCatalog} />
          </>
        ) : null}
        <SearchPanel
          catalog={searchCatalog}
          isLoadingCatalog={isLoadingSearchCatalog}
          savedSearches={savedSearches}
          onSearch={handleSearch}
          onSaveSearch={handleSaveSearch}
          onViewSavedSearch={handleViewSavedSearch}
          onRefreshSavedSearch={handleRefreshSavedSearch}
          onDeleteSavedSearch={handleDeleteSavedSearch}
          onAddFromSearch={handleAddFromSearch}
        />
        <WatchlistPanel items={watchlist} onAddByLotNumber={handleAddByLotNumber} onRemove={handleRemoveWatchlistItem} />
      </DashboardShell>
      <PushSettingsModal
        isOpen={isSettingsOpen}
        subscriptions={subscriptions}
        permissionState={permissionState}
        onSubscribe={handleSubscribePush}
        onUnsubscribe={handleUnsubscribePush}
        onClose={() => setIsSettingsOpen(false)}
      />
    </>
  );
}
