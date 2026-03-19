import type { CSSProperties, ReactNode } from "react";

import { AsyncStatus } from "../shared/AsyncStatus";
import type { User } from "../../types";

type Props = {
  user: User;
  isBrowserOffline: boolean;
  isBootstrapping: boolean;
  isPullToRefreshEnabled: boolean;
  pullToRefreshPhase: "idle" | "pulling" | "armed" | "refreshing";
  pullToRefreshStyle: CSSProperties;
  isAccountMenuOpen: boolean;
  onToggleAccountMenu: () => void;
  children: ReactNode;
};

export function DashboardShell({
  user,
  isBrowserOffline,
  isBootstrapping,
  isPullToRefreshEnabled,
  pullToRefreshPhase,
  pullToRefreshStyle,
  isAccountMenuOpen,
  onToggleAccountMenu,
  children,
}: Props) {
  const isPullToRefreshVisible = isPullToRefreshEnabled && pullToRefreshPhase !== "idle";
  const pullToRefreshTitle =
    pullToRefreshPhase === "refreshing"
      ? "Refreshing dashboard"
      : pullToRefreshPhase === "armed"
        ? "Release to refresh"
        : "Pull to refresh";
  const pullToRefreshMessage =
    pullToRefreshPhase === "refreshing"
      ? "Reloading watchlist, saved searches, and live-sync status."
      : "Drag down from the top edge to reload dashboard data.";

  return (
    <>
      {isPullToRefreshEnabled ? (
        <div
          className={`pull-refresh-indicator${isPullToRefreshVisible ? " pull-refresh-indicator--visible" : ""}`}
          style={pullToRefreshStyle}
          aria-live="polite"
        >
          <p className="pull-refresh-indicator__title">{pullToRefreshTitle}</p>
          <p className="pull-refresh-indicator__message">{pullToRefreshMessage}</p>
          <span className="pull-refresh-indicator__bar" aria-hidden="true" />
        </div>
      ) : null}
      <main
        className={`app-shell app-shell--premium${isPullToRefreshEnabled ? " app-shell--pullable" : ""}${
          pullToRefreshPhase === "pulling" || pullToRefreshPhase === "armed" ? " app-shell--pulling" : ""
        }`}
        style={pullToRefreshStyle}
      >
        <header className="dashboard-header">
          <div className="dashboard-header__copy">
            <p className="eyebrow">Auction Control</p>
            <h1>CarTrap dispatch board</h1>
            <p className="lede">Saved-search inbox, watchlist urgency, and account controls for this device.</p>
          </div>
          <div className="dashboard-header__actions">
            <span className="status-pill">{user.role}</span>
            <button
              type="button"
              className="ghost-button dashboard-header__menu-button"
              aria-expanded={isAccountMenuOpen}
              aria-haspopup="dialog"
              aria-label="Open account menu"
              onClick={onToggleAccountMenu}
            >
              Menu
            </button>
          </div>
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
        <section className="dashboard-grid">{children}</section>
      </main>
    </>
  );
}
