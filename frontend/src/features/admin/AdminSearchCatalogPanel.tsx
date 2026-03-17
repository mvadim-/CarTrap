import { useState } from "react";

import type { SearchCatalog } from "../../types";
import { AsyncStatus } from "../shared/AsyncStatus";

type Props = {
  catalog: SearchCatalog | null;
  loadError: string | null;
  isLoading: boolean;
  isRefreshing: boolean;
  onRefresh: () => Promise<void>;
  onRetryLoad: () => Promise<void>;
};

function formatTimestamp(value: string | null): string {
  if (!value) {
    return "unknown";
  }
  return new Date(value).toLocaleString();
}

export function AdminSearchCatalogPanel({
  catalog,
  loadError,
  isLoading,
  isRefreshing,
  onRefresh,
  onRetryLoad,
}: Props) {
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleRefresh() {
    setMessage(null);
    setError(null);
    try {
      await onRefresh();
      setMessage("Search catalog refresh completed.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not refresh search catalog.");
    }
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Admin</p>
          <h2>Search Catalog</h2>
        </div>
      </div>
      {isLoading && !catalog ? (
        <AsyncStatus
          progress="spinner"
          title="Loading catalog diagnostics"
          message="Catalog freshness and make/model counts are loading."
          className="panel-status"
        />
      ) : null}
      {loadError ? (
        <AsyncStatus
          tone="error"
          title="Catalog diagnostics unavailable"
          message={loadError}
          action={
            <button type="button" className="ghost-button" onClick={() => void onRetryLoad()}>
              Retry catalog
            </button>
          }
          className="panel-status"
        />
      ) : null}
      {error ? <AsyncStatus tone="error" message={error} className="panel-status" /> : null}
      {message ? <AsyncStatus compact tone="success" message={message} className="panel-status" /> : null}
      <dl className="detail-grid detail-grid--single admin-panel__details">
        <div className="detail-item detail-item--stack">
          <dt className="detail-label">Summary:</dt>
          <dd className="detail-value">
            {catalog
              ? `${catalog.summary.make_count} makes · ${catalog.summary.assigned_model_count} assigned models · ${catalog.summary.unassigned_model_count} unassigned`
              : "Catalog not loaded yet."}
          </dd>
        </div>
        <div className="detail-item">
          <dt className="detail-label">Generated:</dt>
          <dd className="detail-value">{formatTimestamp(catalog?.generated_at ?? null)}</dd>
        </div>
        <div className="detail-item">
          <dt className="detail-label">Updated:</dt>
          <dd className="detail-value">{formatTimestamp(catalog?.updated_at ?? null)}</dd>
        </div>
        <div className="detail-item">
          <dt className="detail-label">Overrides:</dt>
          <dd className="detail-value">{catalog?.manual_override_count ?? "—"}</dd>
        </div>
      </dl>
      <button type="button" onClick={() => void handleRefresh()} disabled={isRefreshing} aria-busy={isRefreshing}>
        {isRefreshing ? "Refreshing..." : "Refresh Search Catalog"}
      </button>
      {isRefreshing ? (
        <AsyncStatus
          compact
          progress="bar"
          title="Refreshing catalog"
          message="Existing catalog metadata stays visible until the updated snapshot returns."
          className="panel-status"
        />
      ) : null}
    </section>
  );
}
