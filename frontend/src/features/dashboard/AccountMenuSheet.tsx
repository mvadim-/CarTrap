import { useEffect } from "react";
import { createPortal } from "react-dom";

import type { LiveSyncStatus, ReliabilityDiagnostics, User } from "../../types";
import { useBodyScrollLock } from "../shared/useBodyScrollLock";

type Props = {
  isOpen: boolean;
  user: User;
  liveSyncStatus: LiveSyncStatus | null;
  diagnostics: ReliabilityDiagnostics;
  onClose: () => void;
  onOpenSettings: () => void;
  onLogout: () => void;
};

function formatTimestamp(value: string | null): string {
  if (!value) {
    return "Not available";
  }
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function AccountMenuSheet({
  isOpen,
  user,
  liveSyncStatus,
  diagnostics,
  onClose,
  onOpenSettings,
  onLogout,
}: Props) {
  useBodyScrollLock(isOpen);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) {
    return null;
  }

  const isAdmin = user.role === "admin";
  const liveSyncTone = liveSyncStatus?.status === "degraded" ? "Needs attention" : "Working normally";
  const liveSyncLabel = liveSyncStatus?.status === "degraded" ? "Issue" : "Working";

  const sheet = (
    <div className="modal-backdrop modal-backdrop--sheet" onClick={onClose}>
      <div
        aria-modal="true"
        aria-label="Account menu"
        className="modal-card account-menu-sheet"
        role="dialog"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header account-menu-sheet__header">
          <div>
            <p className="eyebrow">Account</p>
            <h3>{user.email}</h3>
          </div>
          <button type="button" className="ghost-button" onClick={onClose}>
            Close
          </button>
        </div>
        <div className="modal-body account-menu-sheet__body">
          <section className="account-menu-sheet__card" aria-label="Signed-in account">
            <p className="detail-label">Access</p>
            <div className="account-menu-sheet__identity">
              <p className="account-menu-sheet__email">{user.email}</p>
              <span className="status-pill">{user.role}</span>
            </div>
            <p className="muted">Manage connected accounts and notifications in Settings.</p>
          </section>

          {isAdmin ? (
            <>
              <section className="account-menu-sheet__card" aria-label="System status">
                <div className="account-menu-sheet__status-header">
                  <div>
                    <p className="detail-label">Live updates</p>
                    <p className="account-menu-sheet__status-value">{liveSyncTone}</p>
                  </div>
                  <span
                    className={`status-pill${liveSyncStatus?.status === "degraded" ? " account-menu-sheet__pill--warning" : ""}`}
                  >
                    {liveSyncLabel}
                  </span>
                </div>
                <dl className="detail-grid detail-grid--single">
                  <div className="detail-item detail-item--stack">
                    <dt className="detail-label">Last successful update</dt>
                    <dd className="detail-value">{formatTimestamp(liveSyncStatus?.last_success_at ?? null)}</dd>
                  </div>
                  <div className="detail-item detail-item--stack">
                    <dt className="detail-label">Last problem</dt>
                    <dd className="detail-value">{formatTimestamp(liveSyncStatus?.last_failure_at ?? null)}</dd>
                  </div>
                  {liveSyncStatus?.last_error_message ? (
                    <div className="detail-item detail-item--stack">
                      <dt className="detail-label">What went wrong</dt>
                      <dd className="detail-value">{liveSyncStatus.last_error_message}</dd>
                    </div>
                  ) : null}
                </dl>
              </section>

              <section className="account-menu-sheet__card" aria-label="Items to review">
                <div className="account-menu-sheet__status-header">
                  <div>
                    <p className="detail-label">Items to review</p>
                    <p className="account-menu-sheet__status-value">
                      {diagnostics.total_attention > 0 ? `${diagnostics.total_attention} items may need attention` : "Everything looks good"}
                    </p>
                  </div>
                  <span className={`status-pill${diagnostics.total_attention > 0 ? " account-menu-sheet__pill--warning" : ""}`}>
                    Review
                  </span>
                </div>
                <dl className="detail-grid detail-grid--single">
                  <div className="detail-item detail-item--stack">
                    <dt className="detail-label">Saved searches</dt>
                    <dd className="detail-value">
                      {diagnostics.saved_searches.attention} may need attention, {diagnostics.saved_searches.cached} using saved
                      data, {diagnostics.saved_searches.outdated} out of date
                    </dd>
                  </div>
                  <div className="detail-item detail-item--stack">
                    <dt className="detail-label">Tracked lots</dt>
                    <dd className="detail-value">
                      {diagnostics.watchlist.attention} may need attention, {diagnostics.watchlist.cached} using saved data,{" "}
                      {diagnostics.watchlist.outdated} out of date
                    </dd>
                  </div>
                  <div className="detail-item detail-item--stack">
                    <dt className="detail-label">Update queue</dt>
                    <dd className="detail-value">
                      {diagnostics.saved_searches.retryable_failures + diagnostics.watchlist.retryable_failures} retrying,{" "}
                      {diagnostics.saved_searches.repair_pending + diagnostics.watchlist.repair_pending} being fixed,{" "}
                      {diagnostics.saved_searches.failed + diagnostics.watchlist.failed} need manual help
                    </dd>
                  </div>
                </dl>
              </section>
            </>
          ) : null}

          <div className="account-menu-sheet__actions">
            <button
              type="button"
              className="ghost-button"
              onClick={() => {
                onClose();
                onOpenSettings();
              }}
            >
              Settings
            </button>
            <button
              type="button"
              className="ghost-button"
              onClick={() => {
                onClose();
                onLogout();
              }}
            >
              Log Out
            </button>
          </div>
        </div>
      </div>
    </div>
  );

  return typeof document !== "undefined" ? createPortal(sheet, document.body) : sheet;
}
