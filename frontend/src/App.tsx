import { useEffect, useState } from "react";

import { DashboardShell } from "./features/dashboard/DashboardShell";
import { AdminInvitesPanel } from "./features/admin/AdminInvitesPanel";
import { InviteAcceptScreen } from "./features/auth/InviteAcceptScreen";
import { LoginScreen } from "./features/auth/LoginScreen";
import { PushPanel } from "./features/push/PushPanel";
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
  listPushSubscriptions,
  listWatchlist,
  login,
  removeWatchlistItem,
  searchLots,
  subscribeToPush,
  unsubscribeFromPush,
} from "./lib/api";
import type { Invite, PushSubscriptionItem, SearchResult, WatchlistItem } from "./types";

function getNotificationPermission(): string {
  return typeof Notification === "undefined" ? "unsupported" : Notification.permission;
}

export function App() {
  const [routeState, navigate] = useHashRoute();
  const session = useSession();
  const [error, setError] = useState<string | null>(null);
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [inviteLink, setInviteLink] = useState<string | null>(null);
  const [subscriptions, setSubscriptions] = useState<PushSubscriptionItem[]>([]);
  const [permissionState, setPermissionState] = useState(getNotificationPermission());

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
        setWatchlist([]);
        setSubscriptions([]);
        setError("Session expired. Please sign in again.");
        navigate("/login");
      },
    });
  }, [navigate, session]);

  useEffect(() => {
    if (!session.accessToken) {
      return;
    }
    void listWatchlist(session.accessToken).then(setWatchlist).catch(() => undefined);
    void listPushSubscriptions(session.accessToken).then(setSubscriptions).catch(() => undefined);
  }, [session.accessToken]);

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

  async function handleSearch(make: string, model: string, yearFrom: string, yearTo: string) {
    if (!session.accessToken) return;
    try {
      setError(null);
      const results = await searchLots(
        {
          make,
          model,
          year_from: yearFrom ? Number(yearFrom) : undefined,
          year_to: yearTo ? Number(yearTo) : undefined,
        },
        session.accessToken,
      );
      setSearchResults(results);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Search failed");
    }
  }

  async function handleAddFromSearch(lotUrl: string) {
    if (!session.accessToken) return;
    try {
      const trackedLot = await addFromSearch(lotUrl, session.accessToken);
      setWatchlist((current) => [trackedLot, ...current.filter((item) => item.id !== trackedLot.id)]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not add lot");
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
      setWatchlist((current) => [trackedLot, ...current.filter((item) => item.id !== trackedLot.id)]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not add lot");
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

  async function handleSubscribePush() {
    if (!session.accessToken) return;
    if (typeof Notification === "undefined") {
      setPermissionState("unsupported");
      return;
    }
    const permission = await Notification.requestPermission();
    setPermissionState(permission);
    if (permission !== "granted") {
      return;
    }
    const fakeSubscription = {
      endpoint: `${window.location.origin}/push/${session.user?.id ?? "anonymous"}`,
      expirationTime: null,
      keys: { p256dh: "demo-p256dh", auth: "demo-auth" },
    } as PushSubscription;
    const created = await subscribeToPush(fakeSubscription, navigator.userAgent, session.accessToken);
    setSubscriptions((current) => [created, ...current.filter((item) => item.endpoint !== created.endpoint)]);
  }

  async function handleUnsubscribePush(endpoint: string) {
    if (!session.accessToken) return;
    await unsubscribeFromPush(endpoint, session.accessToken);
    setSubscriptions((current) => current.filter((item) => item.endpoint !== endpoint));
  }

  function handleLogout() {
    session.logout();
    setSearchResults([]);
    setWatchlist([]);
    setSubscriptions([]);
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
    <DashboardShell user={session.user!} onLogout={handleLogout}>
      {session.user?.role === "admin" ? (
        <AdminInvitesPanel inviteLink={inviteLink} onCreateInvite={handleCreateInvite} />
      ) : null}
      <SearchPanel results={searchResults} onSearch={handleSearch} onAddFromSearch={handleAddFromSearch} />
      <WatchlistPanel items={watchlist} onAddByLotNumber={handleAddByLotNumber} onRemove={handleRemoveWatchlistItem} />
      <PushPanel
        subscriptions={subscriptions}
        permissionState={permissionState}
        onSubscribe={handleSubscribePush}
        onUnsubscribe={handleUnsubscribePush}
      />
    </DashboardShell>
  );
}
