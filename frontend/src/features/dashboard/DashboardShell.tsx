import type { ReactNode } from "react";

import type { User } from "../../types";

type Props = {
  user: User;
  onLogout: () => void;
  children: ReactNode;
};

export function DashboardShell({ user, onLogout, children }: Props) {
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
          <span className="status-pill">{user.role}</span>
          <strong>{user.email}</strong>
          <button type="button" className="ghost-button" onClick={onLogout}>
            Log Out
          </button>
        </div>
      </header>
      <section className="dashboard-grid">{children}</section>
    </main>
  );
}
