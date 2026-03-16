import type { ReactNode } from "react";

import type { LiveSyncStatus, User } from "../../types";

type Props = {
  user: User;
  liveSyncStatus: LiveSyncStatus | null;
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

export function DashboardShell({ user, liveSyncStatus, onLogout, onOpenSettings, children }: Props) {
  const showOfflineBanner = liveSyncStatus?.status === "degraded";
  const syncTimestampLabel = liveSyncStatus ? formatLastSyncLabel(liveSyncStatus) : null;

  return (
    <main className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Auction Control</p>
          <h1>CarTrap dispatch board</h1>
          <p className="lede">
            Track live lots, promote the right findings to watchlists, and keep every invited user in sync.
          </p>
        </div>
        <div className="hero-card">
          <div className="hero-card__header">
            <p className="eyebrow">User</p>
            <span className="status-pill">{user.role}</span>
          </div>
          <dl className="detail-grid detail-grid--single">
            <div className="detail-item detail-item--stack">
              <dt className="detail-label">Email:</dt>
              <dd className="detail-value">{user.email}</dd>
            </div>
          </dl>
          <div className="hero-card__actions">
            <button type="button" className="ghost-button" onClick={onOpenSettings}>
              Settings
            </button>
            <button type="button" className="ghost-button" onClick={onLogout}>
              Log Out
            </button>
          </div>
        </div>
      </header>
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
