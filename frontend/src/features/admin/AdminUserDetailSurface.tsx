import { useMemo, useState } from "react";
import { createPortal } from "react-dom";

import type { AdminUserActionPayload, AdminUserActionResponse, AdminUserDetail } from "../../types";
import { AsyncStatus } from "../shared/AsyncStatus";
import { shouldUseMobileFullscreen } from "../shared/mobileFullscreen";
import { useBodyScrollLock } from "../shared/useBodyScrollLock";
import { AdminActionConfirmDialog } from "./AdminActionConfirmDialog";
import { formatAdminCurrency, formatAdminTimestamp } from "./adminFormatting";

type Props = {
  isOpen: boolean;
  detail: AdminUserDetail | null;
  isLoading: boolean;
  error: string | null;
  isRunningAction: boolean;
  actionResult: AdminUserActionResponse | null;
  actionError: string | null;
  onClose: () => void;
  onRetry: () => Promise<void>;
  onRunAction: (action: string, payload: AdminUserActionPayload) => Promise<void>;
};

type PendingConfirm = {
  title: string;
  message: string;
  confirmLabel: string;
  action: string;
  payload: AdminUserActionPayload;
} | null;

export function AdminUserDetailSurface({
  isOpen,
  detail,
  isLoading,
  error,
  isRunningAction,
  actionResult,
  actionError,
  onClose,
  onRetry,
  onRunAction,
}: Props) {
  const [pendingConfirm, setPendingConfirm] = useState<PendingConfirm>(null);
  const isMobileFullscreen = shouldUseMobileFullscreen() || (typeof window !== "undefined" && window.innerWidth <= 1180);
  const hasContent = isLoading || error || detail;

  useBodyScrollLock(isOpen && isMobileFullscreen);

  const safeActions = useMemo(() => {
    if (!detail) {
      return [];
    }
    return [
      detail.account.status === "blocked"
        ? { label: "Unblock user", action: "unblock", tone: "default" }
        : { label: "Block user", action: "block", tone: "danger" },
      detail.account.role === "admin"
        ? { label: "Demote to user", action: "demote", tone: "danger" }
        : { label: "Promote to admin", action: "promote", tone: "default" },
      { label: "Reset password", action: "reset_password", tone: "danger" },
    ];
  }, [detail]);

  if (!isOpen || !hasContent) {
    return null;
  }

  function openConfirm(title: string, message: string, confirmLabel: string, action: string, payload: AdminUserActionPayload = {}) {
    setPendingConfirm({ title, message, confirmLabel, action, payload });
  }

  async function handleConfirm() {
    if (!pendingConfirm) {
      return;
    }
    await onRunAction(pendingConfirm.action, pendingConfirm.payload);
    setPendingConfirm(null);
  }

  const surface = (
    <>
      <div className={`admin-detail-backdrop${isMobileFullscreen ? " admin-detail-backdrop--modal" : ""}`} onClick={onClose}>
        <aside
          className={`admin-detail-surface${isMobileFullscreen ? " admin-detail-surface--modal" : ""}`}
          role="complementary"
          aria-label="Admin user detail"
          onClick={(event) => event.stopPropagation()}
        >
          <div className="admin-detail-surface__header">
            <div>
              <p className="eyebrow">User detail</p>
              <h3>{detail?.account.email ?? "Loading user"}</h3>
            </div>
            <button type="button" className="ghost-button" onClick={onClose}>
              Close
            </button>
          </div>

          {isLoading && !detail ? (
            <AsyncStatus progress="spinner" title="Loading user detail" message="Collecting account and resource data." className="panel-status" />
          ) : null}
          {error ? (
            <AsyncStatus
              tone="error"
              title="Couldn't load user detail"
              message={error}
              action={
                <button type="button" className="ghost-button" onClick={() => void onRetry()}>
                  Try again
                </button>
              }
              className="panel-status"
            />
          ) : null}
          {actionError ? <AsyncStatus tone="error" title="Action failed" message={actionError} className="panel-status" /> : null}
          {actionResult ? (
            <AsyncStatus
              compact
              tone="success"
              message={
                actionResult.generated_password
                  ? `${actionResult.message} Temporary password: ${actionResult.generated_password}`
                  : actionResult.message
              }
              className="panel-status"
            />
          ) : null}

          {detail ? (
            <div className="admin-detail-surface__body">
              <section className="admin-detail-section">
                <div className="panel-header">
                  <div>
                    <p className="eyebrow">Account</p>
                    <h4>{detail.account.email}</h4>
                  </div>
                </div>
                <dl className="detail-grid detail-grid--single">
                  <div className="detail-item">
                    <dt className="detail-label">Role</dt>
                    <dd className="detail-value">{detail.account.role}</dd>
                  </div>
                  <div className="detail-item">
                    <dt className="detail-label">Status</dt>
                    <dd className="detail-value">{detail.account.status}</dd>
                  </div>
                  <div className="detail-item">
                    <dt className="detail-label">Created</dt>
                    <dd className="detail-value">{formatAdminTimestamp(detail.account.created_at)}</dd>
                  </div>
                  <div className="detail-item">
                    <dt className="detail-label">Last login</dt>
                    <dd className="detail-value">{formatAdminTimestamp(detail.account.last_login_at)}</dd>
                  </div>
                </dl>
                <div className="admin-detail-actions">
                  {safeActions.map((item) => (
                    <button
                      key={item.action}
                      type="button"
                      className={item.tone === "danger" ? "danger-button" : "ghost-button"}
                      disabled={isRunningAction}
                      onClick={() =>
                        openConfirm(item.label, `${item.label} for ${detail.account.email}?`, item.label, item.action)
                      }
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              </section>

              <section className="admin-detail-section">
                <div className="panel-header">
                  <div>
                    <p className="eyebrow">Invites</p>
                    <h4>Invite history</h4>
                  </div>
                </div>
                <div className="admin-detail-list">
                  {detail.invites.map((invite) => (
                    <div key={invite.id} className="admin-detail-list__item">
                      <strong>{invite.status}</strong>
                      <span>{formatAdminTimestamp(invite.created_at ?? invite.expires_at)}</span>
                    </div>
                  ))}
                  {detail.invites.length === 0 ? <p className="muted">No invite records for this email.</p> : null}
                </div>
              </section>

              <section className="admin-detail-section">
                <div className="panel-header">
                  <div>
                    <p className="eyebrow">Providers</p>
                    <h4>Provider connections</h4>
                  </div>
                </div>
                <div className="admin-detail-list">
                  {detail.provider_connections.map((connection) => (
                    <div key={connection.id} className="admin-detail-list__item admin-detail-list__item--split">
                      <div>
                        <strong>{connection.provider_label ?? connection.provider.toUpperCase()}</strong>
                        <p className="muted">{connection.account_label ?? "No account label"}</p>
                      </div>
                      <div className="admin-detail-list__actions">
                        <span>{connection.status}</span>
                        <button
                          type="button"
                          className="ghost-button"
                          disabled={isRunningAction}
                          onClick={() =>
                            openConfirm(
                              "Disconnect provider",
                              `Disconnect ${connection.provider_label ?? connection.provider} for ${detail.account.email}?`,
                              "Disconnect provider",
                              "disconnect_provider",
                              { provider: connection.provider },
                            )
                          }
                        >
                          Disconnect
                        </button>
                      </div>
                    </div>
                  ))}
                  {detail.provider_connections.length === 0 ? <p className="muted">No provider connections.</p> : null}
                </div>
                {detail.provider_connections.length > 1 ? (
                  <button
                    type="button"
                    className="danger-button"
                    disabled={isRunningAction}
                    onClick={() =>
                      openConfirm(
                        "Disconnect all providers",
                        `Disconnect all provider connections for ${detail.account.email}?`,
                        "Disconnect all providers",
                        "disconnect_all_providers",
                      )
                    }
                  >
                    Disconnect all providers
                  </button>
                ) : null}
              </section>

              <section className="admin-detail-section">
                <div className="panel-header">
                  <div>
                    <p className="eyebrow">Saved searches</p>
                    <h4>{detail.saved_searches.length} saved searches</h4>
                  </div>
                </div>
                <div className="admin-detail-list">
                  {detail.saved_searches.map((item) => (
                    <div key={item.id} className="admin-detail-list__item admin-detail-list__item--split">
                      <div>
                        <strong>{item.label}</strong>
                        <p className="muted">
                          {item.providers.join(", ")} · {item.new_count} new · last sync {formatAdminTimestamp(item.last_synced_at)}
                        </p>
                      </div>
                      <button
                        type="button"
                        className="ghost-button"
                        disabled={isRunningAction}
                        onClick={() =>
                          openConfirm(
                            "Delete saved search",
                            `Delete "${item.label}" for ${detail.account.email}?`,
                            "Delete saved search",
                            "delete_saved_search",
                            { resource_id: item.id },
                          )
                        }
                      >
                        Delete
                      </button>
                    </div>
                  ))}
                  {detail.saved_searches.length === 0 ? <p className="muted">No saved searches.</p> : null}
                </div>
                {detail.saved_searches.length > 0 ? (
                  <button
                    type="button"
                    className="danger-button"
                    disabled={isRunningAction}
                    onClick={() =>
                      openConfirm(
                        "Delete all saved searches",
                        `Delete all saved searches for ${detail.account.email}?`,
                        "Delete all saved searches",
                        "delete_all_saved_searches",
                      )
                    }
                  >
                    Delete all saved searches
                  </button>
                ) : null}
              </section>

              <section className="admin-detail-section">
                <div className="panel-header">
                  <div>
                    <p className="eyebrow">Tracked lots</p>
                    <h4>{detail.tracked_lots.length} tracked lots</h4>
                  </div>
                </div>
                <div className="admin-detail-list">
                  {detail.tracked_lots.map((item) => (
                    <div key={item.id} className="admin-detail-list__item admin-detail-list__item--split">
                      <div>
                        <strong>{item.title}</strong>
                        <p className="muted">
                          {item.provider.toUpperCase()} · {item.lot_number} · {formatAdminCurrency(item.current_bid, item.currency)}
                        </p>
                      </div>
                      <div className="admin-detail-list__actions">
                        <button
                          type="button"
                          className="ghost-button"
                          disabled={isRunningAction}
                          onClick={() =>
                            openConfirm(
                              "Purge snapshots",
                              `Purge change-history snapshots for ${item.title}?`,
                              "Purge snapshots",
                              "purge_snapshots",
                              { resource_id: item.id },
                            )
                          }
                        >
                          Purge snapshots
                        </button>
                        <button
                          type="button"
                          className="ghost-button"
                          disabled={isRunningAction}
                          onClick={() =>
                            openConfirm(
                              "Delete tracked lot",
                              `Delete tracked lot ${item.lot_number} for ${detail.account.email}?`,
                              "Delete tracked lot",
                              "delete_tracked_lot",
                              { resource_id: item.id },
                            )
                          }
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  ))}
                  {detail.tracked_lots.length === 0 ? <p className="muted">No tracked lots.</p> : null}
                </div>
                {detail.tracked_lots.length > 0 ? (
                  <div className="admin-detail-actions">
                    <button
                      type="button"
                      className="ghost-button"
                      disabled={isRunningAction}
                      onClick={() =>
                        openConfirm(
                          "Purge all snapshots",
                          `Purge all lot snapshots for ${detail.account.email}?`,
                          "Purge all snapshots",
                          "purge_snapshots",
                        )
                      }
                    >
                      Purge all snapshots
                    </button>
                    <button
                      type="button"
                      className="danger-button"
                      disabled={isRunningAction}
                      onClick={() =>
                        openConfirm(
                          "Delete all tracked lots",
                          `Delete all tracked lots for ${detail.account.email}?`,
                          "Delete all tracked lots",
                          "delete_all_tracked_lots",
                        )
                      }
                    >
                      Delete all tracked lots
                    </button>
                  </div>
                ) : null}
              </section>

              <section className="admin-detail-section">
                <div className="panel-header">
                  <div>
                    <p className="eyebrow">Push devices</p>
                    <h4>{detail.push_subscriptions.length} push subscriptions</h4>
                  </div>
                </div>
                <div className="admin-detail-list">
                  {detail.push_subscriptions.map((item) => (
                    <div key={item.id} className="admin-detail-list__item admin-detail-list__item--split">
                      <div>
                        <strong>{item.user_agent ?? "Unknown device"}</strong>
                        <p className="muted">{item.endpoint}</p>
                      </div>
                      <button
                        type="button"
                        className="ghost-button"
                        disabled={isRunningAction}
                        onClick={() =>
                          openConfirm(
                            "Delete push subscription",
                            `Delete this push subscription for ${detail.account.email}?`,
                            "Delete push subscription",
                            "delete_push_subscription",
                            { resource_id: item.id },
                          )
                        }
                      >
                        Delete
                      </button>
                    </div>
                  ))}
                  {detail.push_subscriptions.length === 0 ? <p className="muted">No push subscriptions.</p> : null}
                </div>
                {detail.push_subscriptions.length > 0 ? (
                  <button
                    type="button"
                    className="danger-button"
                    disabled={isRunningAction}
                    onClick={() =>
                      openConfirm(
                        "Delete all push subscriptions",
                        `Delete all push subscriptions for ${detail.account.email}?`,
                        "Delete all push subscriptions",
                        "delete_all_push_subscriptions",
                      )
                    }
                  >
                    Delete all push subscriptions
                  </button>
                ) : null}
              </section>

              <section className="admin-detail-section admin-detail-section--danger">
                <div className="panel-header">
                  <div>
                    <p className="eyebrow">Danger zone</p>
                    <h4>Delete user</h4>
                  </div>
                </div>
                <p className="muted">
                  This removes the account plus {detail.danger_zone.saved_searches} saved searches, {detail.danger_zone.tracked_lots} tracked lots,{" "}
                  {detail.danger_zone.push_subscriptions} push subscriptions, and {detail.danger_zone.lot_snapshots} lot snapshots.
                </p>
                <button
                  type="button"
                  className="danger-button"
                  disabled={isRunningAction}
                  onClick={() =>
                    openConfirm(
                      "Delete user and related data",
                      `Delete ${detail.account.email} and all related data?`,
                      "Delete user",
                      "delete_user",
                    )
                  }
                >
                  Delete user
                </button>
              </section>
            </div>
          ) : null}
        </aside>
      </div>
      <AdminActionConfirmDialog
        isOpen={pendingConfirm !== null}
        title={pendingConfirm?.title ?? "Confirm action"}
        message={pendingConfirm?.message ?? ""}
        confirmLabel={pendingConfirm?.confirmLabel ?? "Confirm"}
        isPending={isRunningAction}
        onClose={() => setPendingConfirm(null)}
        onConfirm={handleConfirm}
      />
    </>
  );

  return typeof document !== "undefined" ? createPortal(surface, document.body) : surface;
}
