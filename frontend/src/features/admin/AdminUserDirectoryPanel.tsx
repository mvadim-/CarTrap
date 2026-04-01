import type { AdminUserDirectoryRow, AdminUserFilters } from "../../types";
import { AsyncStatus } from "../shared/AsyncStatus";
import { formatAdminShortDate, formatAdminTimestamp } from "./adminFormatting";

type Props = {
  rows: AdminUserDirectoryRow[];
  total: number;
  selectedUserId: string | null;
  filters: AdminUserFilters;
  isLoading: boolean;
  error: string | null;
  onRetry: () => Promise<void>;
  onSelectUser: (userId: string) => void;
  onFiltersChange: (patch: Partial<AdminUserFilters>) => void;
};

export function AdminUserDirectoryPanel({
  rows,
  total,
  selectedUserId,
  filters,
  isLoading,
  error,
  onRetry,
  onSelectUser,
  onFiltersChange,
}: Props) {
  return (
    <section className="panel panel--support admin-directory-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Directory</p>
          <h2>User Directory</h2>
          <p className="panel-header__lede">Search, filter, and inspect one user without leaving the dashboard shell.</p>
        </div>
      </div>

      <div className="admin-directory-toolbar">
        <label className="admin-directory-toolbar__search">
          <span className="sr-only">Search users</span>
          <input
            aria-label="Search users"
            placeholder="Search email"
            value={filters.query}
            onChange={(event) => onFiltersChange({ query: event.target.value, page: 1 })}
          />
        </label>
        <label>
          <span className="sr-only">Role filter</span>
          <select aria-label="Role filter" value={filters.role} onChange={(event) => onFiltersChange({ role: event.target.value as AdminUserFilters["role"], page: 1 })}>
            <option value="any">All roles</option>
            <option value="admin">Admins</option>
            <option value="user">Users</option>
          </select>
        </label>
        <label>
          <span className="sr-only">Status filter</span>
          <select aria-label="Status filter" value={filters.status} onChange={(event) => onFiltersChange({ status: event.target.value as AdminUserFilters["status"], page: 1 })}>
            <option value="any">Any status</option>
            <option value="active">Active</option>
            <option value="blocked">Blocked</option>
            <option value="disabled">Disabled</option>
          </select>
        </label>
        <label>
          <span className="sr-only">Provider filter</span>
          <select
            aria-label="Provider filter"
            value={filters.provider_state}
            onChange={(event) => onFiltersChange({ provider_state: event.target.value as AdminUserFilters["provider_state"], page: 1 })}
          >
            <option value="any">Any provider state</option>
            <option value="none">No providers</option>
            <option value="connected">Connected</option>
            <option value="reconnect_required">Reconnect required</option>
            <option value="disconnected">Disconnected</option>
            <option value="error">Error</option>
          </select>
        </label>
        <label>
          <span className="sr-only">Push filter</span>
          <select aria-label="Push filter" value={filters.push_state} onChange={(event) => onFiltersChange({ push_state: event.target.value as AdminUserFilters["push_state"], page: 1 })}>
            <option value="any">Any push state</option>
            <option value="has_push">Has push</option>
            <option value="no_push">No push</option>
          </select>
        </label>
        <label>
          <span className="sr-only">Watchlist filter</span>
          <select
            aria-label="Watchlist filter"
            value={filters.watchlist_state}
            onChange={(event) => onFiltersChange({ watchlist_state: event.target.value as AdminUserFilters["watchlist_state"], page: 1 })}
          >
            <option value="any">Any watchlist state</option>
            <option value="has_tracked_lots">Has tracked lots</option>
            <option value="no_tracked_lots">No tracked lots</option>
            <option value="unseen_updates">Unseen updates</option>
          </select>
        </label>
        <label>
          <span className="sr-only">Sort users</span>
          <select aria-label="Sort users" value={filters.sort} onChange={(event) => onFiltersChange({ sort: event.target.value as AdminUserFilters["sort"] })}>
            <option value="created_at_desc">Newest first</option>
            <option value="created_at_asc">Oldest first</option>
            <option value="last_login_desc">Recent login</option>
            <option value="last_login_asc">Oldest login</option>
            <option value="email_asc">Email A-Z</option>
            <option value="email_desc">Email Z-A</option>
          </select>
        </label>
      </div>

      <p className="muted admin-directory-panel__summary">{total} users matched</p>

      {isLoading && rows.length === 0 ? (
        <AsyncStatus progress="spinner" title="Loading user directory" message="Preparing user rows and counters." className="panel-status" />
      ) : null}
      {error ? (
        <AsyncStatus
          tone="error"
          title="Couldn't load user directory"
          message={error}
          action={
            <button type="button" className="ghost-button" onClick={() => void onRetry()}>
              Try again
            </button>
          }
          className="panel-status"
        />
      ) : null}

      <div className="admin-directory-list" aria-label="Admin user directory">
        {rows.map((row) => (
          <button
            key={row.id}
            type="button"
            className={`admin-user-row${selectedUserId === row.id ? " is-selected" : ""}`}
            onClick={() => onSelectUser(row.id)}
          >
            <div className="admin-user-row__identity">
              <strong>{row.email}</strong>
              <span className={`admin-user-row__status admin-user-row__status--${row.status}`}>{row.status}</span>
              {row.flags.has_pending_invite ? <span className="admin-user-row__flag">Invite pending</span> : null}
              {row.flags.has_unseen_watchlist_updates ? <span className="admin-user-row__flag">Watchlist update</span> : null}
            </div>
            <div className="admin-user-row__meta">
              <span>{row.role}</span>
              <span>{row.provider_state.replace(/_/g, " ")}</span>
              <span>{row.counts.saved_searches} saved</span>
              <span>{row.counts.tracked_lots} tracked</span>
              <span>{row.counts.push_subscriptions} push</span>
              <span>Joined {formatAdminShortDate(row.created_at)}</span>
              <span>Last login {formatAdminTimestamp(row.last_login_at)}</span>
            </div>
          </button>
        ))}
        {!isLoading && rows.length === 0 && !error ? <p className="muted">No users matched the current filters.</p> : null}
      </div>
    </section>
  );
}
