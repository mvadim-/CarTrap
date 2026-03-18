import { useEffect } from "react";

import type { SearchResult } from "../../types";
import { AsyncStatus } from "../shared/AsyncStatus";
import { LotThumbnail } from "../shared/LotThumbnail";

type Props = {
  isOpen: boolean;
  title: string;
  results: SearchResult[];
  totalResults: number;
  onClose: () => void;
  onAddFromSearch: (lotUrl: string) => Promise<void>;
  onSaveSearch: () => Promise<void>;
  canSave: boolean;
  isSavingSearch?: boolean;
  addingFromSearchLotUrl?: string | null;
  canRefreshLive?: boolean;
  onRefreshLive?: () => Promise<void>;
  isRefreshingLive?: boolean;
  lastSyncedAt?: string | null;
  refreshError?: string | null;
  statusMessage?: string | null;
};

export function SearchResultsModal({
  isOpen,
  title,
  results,
  totalResults,
  onClose,
  onAddFromSearch,
  onSaveSearch,
  canSave,
  isSavingSearch = false,
  addingFromSearchLotUrl = null,
  canRefreshLive = false,
  onRefreshLive,
  isRefreshingLive = false,
  lastSyncedAt = null,
  refreshError = null,
  statusMessage = null,
}: Props) {
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

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        aria-modal="true"
        className="modal-card"
        role="dialog"
        aria-label="Search results"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <p className="eyebrow">Results</p>
            <h3>{title}</h3>
          </div>
          <div className="modal-toolbar modal-toolbar--results">
            {canSave ? (
              <button
                type="button"
                onClick={() => void onSaveSearch()}
                disabled={!canSave || isSavingSearch}
                aria-busy={isSavingSearch}
              >
                {isSavingSearch ? "Saving..." : "Save Search"}
              </button>
            ) : null}
            {canRefreshLive ? (
              <button
                type="button"
                onClick={() => void onRefreshLive?.()}
                disabled={isRefreshingLive}
                aria-busy={isRefreshingLive}
              >
                {isRefreshingLive ? "Refreshing..." : "Refresh Live"}
              </button>
            ) : null}
            <button type="button" className="ghost-button" onClick={onClose}>
              Close
            </button>
          </div>
        </div>
        <div className="modal-filter-bar">
          <span className="muted">
            {totalResults} {totalResults === 1 ? "lot" : "lots"} found. Current result set stays reopenable until you close it.
          </span>
          {lastSyncedAt ? <span className="muted">Last synced {new Date(lastSyncedAt).toLocaleString()}</span> : null}
        </div>
        {isRefreshingLive ? (
          <AsyncStatus
            compact
            progress="bar"
            title="Refreshing live results"
            message="Cached results stay visible while the latest Copart data loads."
            className="modal-status"
          />
        ) : null}
        {statusMessage ? (
          <AsyncStatus compact tone="success" message={statusMessage} className="modal-status" />
        ) : null}
        {refreshError ? (
          <AsyncStatus
            compact
            tone="error"
            title="Live refresh unavailable"
            message={refreshError}
            className="modal-status"
          />
        ) : null}
        <div className="modal-body result-list">
          {results.length === 0 ? (
            <p className="muted">No lots matched this search.</p>
          ) : (
            results.map((result) => (
              <article key={result.lot_number} className="result-card result-card--media result-card--search">
                <LotThumbnail title={result.title} thumbnailUrl={result.thumbnail_url} />
                <div className="result-copy">
                  <strong>{result.title}</strong>
                  <p className="muted">
                    Lot {result.lot_number} · {result.location ?? "Unknown location"}
                  </p>
                </div>
                <div className="result-actions">
                  {result.is_new ? <span className="new-badge">NEW</span> : null}
                  <span className="status-pill">{result.status}</span>
                  <button
                    type="button"
                    onClick={() => void onAddFromSearch(result.url)}
                    disabled={addingFromSearchLotUrl === result.url}
                    aria-busy={addingFromSearchLotUrl === result.url}
                  >
                    {addingFromSearchLotUrl === result.url ? "Adding..." : "Add to Watchlist"}
                  </button>
                </div>
              </article>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
