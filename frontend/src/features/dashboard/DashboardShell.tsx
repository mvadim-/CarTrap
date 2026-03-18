import type { ReactNode } from "react";

import { AsyncStatus } from "../shared/AsyncStatus";
import type { LiveSyncStatus, User } from "../../types";

type Props = {
  user: User;
  liveSyncStatus: LiveSyncStatus | null;
  isBrowserOffline: boolean;
  isBootstrapping: boolean;
  onLogout: () => void;
  onOpenSettings: () => void;
  children: ReactNode;
};

function formatLastSyncLabel(status: LiveSyncStatus): string | null {
  if (status.last_success_at) {
    return `Last successful sync: ${new Intl.DateTimeFormat(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(status.last_success_at))}`;
  }
  if (status.last_failure_at) {
    return `Last failure: ${new Intl.DateTimeFormat(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(status.last_failure_at))}`;
  }
  return null;
}

export function DashboardShell({
  user,
  liveSyncStatus,
  isBrowserOffline,
  isBootstrapping,
  onLogout,
  onOpenSettings,
  children,
}: Props) {
  const showOfflineBanner = liveSyncStatus?.status === "degraded";
  const syncTimestampLabel = liveSyncStatus ? formatLastSyncLabel(liveSyncStatus) : null;

  return (
    <main className="app-shell app-shell--premium">
      <header className="hero">
        <div className="hero-copy">
          <p className="eyebrow">Auction Control</p>
          <h1>CarTrap dispatch board</h1>
          <p className="lede">
            Track live lots, promote the right findings to watchlists, and keep every invited user in sync.
          </p>
        </div>
        <aside className="hero-card" aria-label="User summary">
          <div className="hero-card__header">
            <p className="eyebrow">User</p>
            <span className="status-pill">{user.role}</span>
          </div>
          <div className="hero-card__identity">
            <p className="detail-label">Email</p>
            <p className="hero-card__email">{user.email}</p>
          </div>
          <div className="hero-card__actions">
            <button type="button" className="ghost-button" onClick={onOpenSettings}>
              Settings
            </button>
            <button type="button" className="ghost-button" onClick={onLogout}>
              Log Out
            </button>
          </div>
        </aside>
      </header>
      {isBootstrapping ? (
        <AsyncStatus
          compact
          progress="bar"
          title="Updating dashboard"
          message="Loading the latest saved searches, watchlist, and device diagnostics."
          className="dashboard-status"
        />
      ) : null}
      {isBrowserOffline ? (
        <section className="live-sync-banner live-sync-banner--offline" aria-live="polite">
          <div>
            <p className="eyebrow">Connection</p>
            <h2>This device is offline.</h2>
            <p className="lede live-sync-banner__copy">
              Previously loaded data stays visible, but live search, watchlist updates, and push diagnostics need a
              connection.
            </p>
          </div>
          <div className="live-sync-banner__meta">
            <p>Reconnect to resume live Copart actions and retry failed requests.</p>
          </div>
        </section>
      ) : null}
      {showOfflineBanner ? (
        <section className="live-sync-banner" aria-live="polite">
          <div>
            <p className="eyebrow">Live Sync</p>
            <h2>Live Copart sync is temporarily unavailable.</h2>
            <p className="lede live-sync-banner__copy">
              Search and watchlist actions that need fresh Copart data may fail. Cached Mongo-backed data remains
              available.
            </p>
          </div>
          <div className="live-sync-banner__meta">
            {syncTimestampLabel ? <p>{syncTimestampLabel}</p> : null}
            {liveSyncStatus?.last_error_message ? <p>{liveSyncStatus.last_error_message}</p> : null}
          </div>
        </section>
      ) : null}
      <section className="dashboard-grid">{children}</section>
    </main>
  );
}
