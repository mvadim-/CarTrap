import type { AdminOverview, AdminSystemHealth } from "../../types";
import { AsyncStatus } from "../shared/AsyncStatus";
import { formatAdminCount, formatAdminTimestamp } from "./adminFormatting";

type Props = {
  overview: AdminOverview | null;
  systemHealth: AdminSystemHealth | null;
  isLoading: boolean;
  error: string | null;
  onRetry: () => Promise<void>;
};

type MetricCardProps = {
  label: string;
  value: string;
  meta: string;
};

function MetricCard({ label, value, meta }: MetricCardProps) {
  return (
    <article className="admin-metric-card">
      <p className="admin-metric-card__label">{label}</p>
      <strong className="admin-metric-card__value">{value}</strong>
      <p className="admin-metric-card__meta">{meta}</p>
    </article>
  );
}

export function AdminOverviewPanel({ overview, systemHealth, isLoading, error, onRetry }: Props) {
  return (
    <section className="panel panel--support admin-overview-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Admin</p>
          <h2>Command Center</h2>
          <p className="panel-header__lede">Platform-wide counters, live-sync health, and operator-facing risk signals.</p>
        </div>
      </div>

      {isLoading && !overview ? (
        <AsyncStatus
          progress="spinner"
          title="Loading admin overview"
          message="Collecting platform metrics and system-health signals."
          className="panel-status"
        />
      ) : null}

      {error ? (
        <AsyncStatus
          tone="error"
          title="Couldn't load admin overview"
          message={error}
          action={
            <button type="button" className="ghost-button" onClick={() => void onRetry()}>
              Try again
            </button>
          }
          className="panel-status"
        />
      ) : null}

      {overview ? (
        <>
          <div className="admin-metric-grid" aria-label="Admin overview metrics">
            <MetricCard
              label="Users"
              value={formatAdminCount(overview.users.total)}
              meta={`${formatAdminCount(overview.users.admins)} admins · ${formatAdminCount(overview.users.blocked)} blocked`}
            />
            <MetricCard
              label="Invites"
              value={formatAdminCount(overview.invites.pending)}
              meta={`${formatAdminCount(overview.invites.expired)} expired · ${formatAdminCount(overview.invites.accepted)} accepted`}
            />
            <MetricCard
              label="Providers"
              value={formatAdminCount(overview.providers.total_connections)}
              meta={`${formatAdminCount(overview.providers.connected)} connected · ${formatAdminCount(overview.providers.reconnect_required)} reconnect required`}
            />
            <MetricCard
              label="Saved Searches"
              value={formatAdminCount(overview.searches.total_saved_searches)}
              meta={`${formatAdminCount(overview.searches.stale_or_problem)} attention · ${formatAdminCount(overview.searches.searches_with_new_matches)} with new matches`}
            />
            <MetricCard
              label="Tracked Lots"
              value={formatAdminCount(overview.watchlist.total_tracked_lots)}
              meta={`${formatAdminCount(overview.watchlist.unseen_updates)} unseen updates · ${formatAdminCount(overview.watchlist.stale_or_problem)} attention`}
            />
            <MetricCard
              label="Push"
              value={formatAdminCount(overview.push.total_subscriptions)}
              meta={`${formatAdminCount(overview.push.users_with_push)} users with push · ${formatAdminCount(overview.push.users_without_push)} without`}
            />
          </div>

          <div className="admin-system-health" aria-label="System health">
            <div>
              <p className="eyebrow">System health</p>
              <h3>{overview.system.live_sync_status === "degraded" ? "Live sync degraded" : "Live sync available"}</h3>
              <p className="muted">
                Last success: {formatAdminTimestamp(overview.system.last_success_at)} · Last failure:{" "}
                {formatAdminTimestamp(overview.system.last_failure_at)}
              </p>
            </div>
            <dl className="detail-grid detail-grid--single admin-overview-panel__health-list">
              <div className="detail-item">
                <dt className="detail-label">Environment</dt>
                <dd className="detail-value">{systemHealth?.environment ?? "—"}</dd>
              </div>
              <div className="detail-item">
                <dt className="detail-label">Blocked users</dt>
                <dd className="detail-value">{formatAdminCount(systemHealth?.blocked_users ?? overview.users.blocked)}</dd>
              </div>
              <div className="detail-item">
                <dt className="detail-label">Reconnect required</dt>
                <dd className="detail-value">{formatAdminCount(systemHealth?.provider_reconnect_required ?? 0)}</dd>
              </div>
              <div className="detail-item">
                <dt className="detail-label">Attention queues</dt>
                <dd className="detail-value">
                  {(systemHealth?.saved_search_attention ?? 0) + (systemHealth?.watchlist_attention ?? 0)}
                </dd>
              </div>
            </dl>
          </div>
        </>
      ) : null}
    </section>
  );
}
