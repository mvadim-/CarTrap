import type { CSSProperties, ReactNode } from "react";

import headerBrandLockup from "../../assets/header-brand/cartrap-auction-lockup.png";
import { AsyncStatus } from "../shared/AsyncStatus";

type Props = {
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
      ? "Updating"
      : pullToRefreshPhase === "armed"
        ? "Release to update"
        : "Pull to update";
  const pullToRefreshMessage =
    pullToRefreshPhase === "refreshing"
      ? "Reloading saved searches, tracked lots, and connection status."
      : "Drag down from the top edge to refresh the page.";

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
            <div className="dashboard-header__kicker">
              <p className="eyebrow">Auction Control</p>
            </div>
            <div className="dashboard-header__title-row">
              <div className="dashboard-header__brand-lockup">
                <img
                  className="dashboard-header__brand-lockup-image"
                  src={headerBrandLockup}
                  alt="CarTrap for Copart and IAAI"
                />
              </div>
              <h1>CarTrap dispatch board</h1>
            </div>
            <p className="lede">Track searches, saved lots, and connected accounts in one place.</p>
          </div>
          <div className="dashboard-header__actions">
            <button
              type="button"
              className="ghost-button dashboard-header__menu-button"
              aria-expanded={isAccountMenuOpen}
              aria-haspopup="dialog"
              aria-label="Open account menu"
              onClick={onToggleAccountMenu}
            >
              <span className="dashboard-header__menu-icon" aria-hidden="true">
                <span />
                <span />
                <span />
              </span>
              <span className="dashboard-header__menu-label">Menu</span>
            </button>
          </div>
        </header>
        {isBootstrapping ? (
          <AsyncStatus
            compact
            progress="bar"
            title="Loading your dashboard"
            message="Getting saved searches, tracked lots, and device settings ready."
            className="dashboard-status"
          />
        ) : null}
        {isBrowserOffline ? (
          <section className="live-sync-banner live-sync-banner--offline" aria-live="polite">
            <div>
              <p className="eyebrow">Connection</p>
              <h2>This device is offline.</h2>
              <p className="lede live-sync-banner__copy">
                You can still see saved information, but new searches and updates need an internet connection.
              </p>
            </div>
            <div className="live-sync-banner__meta">
              <p>Reconnect to keep your searches, tracked lots, and alerts up to date.</p>
            </div>
          </section>
        ) : null}
        <section className="dashboard-grid">{children}</section>
      </main>
    </>
  );
}
