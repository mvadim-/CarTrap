import type { ReactNode } from "react";

import type { User } from "../../types";

type Props = {
  user: User;
  onLogout: () => void;
  onOpenSettings: () => void;
  children: ReactNode;
};

export function DashboardShell({ user, onLogout, onOpenSettings, children }: Props) {
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
      <section className="dashboard-grid">{children}</section>
    </main>
  );
}
