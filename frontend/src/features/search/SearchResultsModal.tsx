import { useEffect } from "react";

import type { SearchResult } from "../../types";
import { LotThumbnail } from "../shared/LotThumbnail";

type Props = {
  isOpen: boolean;
  results: SearchResult[];
  onClose: () => void;
  onAddFromSearch: (lotUrl: string) => Promise<void>;
  onSaveSearch: () => Promise<void>;
  canSave: boolean;
};

export function SearchResultsModal({ isOpen, results, onClose, onAddFromSearch, onSaveSearch, canSave }: Props) {
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
            <h3>Copart Search Results</h3>
          </div>
          <div className="modal-toolbar">
            <button type="button" className="ghost-button" onClick={() => void onSaveSearch()} disabled={!canSave}>
              Save Search
            </button>
            <button type="button" className="ghost-button" onClick={onClose}>
              Close
            </button>
          </div>
        </div>
        <div className="modal-filter-bar">
          <span className="muted">Filters will live here next. Current result set stays reopenable until you close it.</span>
        </div>
        <div className="modal-body result-list">
          {results.length === 0 ? (
            <p className="muted">No lots matched this search.</p>
          ) : (
            results.map((result) => (
              <article key={result.lot_number} className="result-card result-card--media">
                <LotThumbnail title={result.title} thumbnailUrl={result.thumbnail_url} />
                <div className="result-copy">
                  <strong>{result.title}</strong>
                  <p className="muted">
                    Lot {result.lot_number} · {result.location ?? "Unknown location"}
                  </p>
                </div>
                <div className="result-actions">
                  <span className="status-pill">{result.status}</span>
                  <button type="button" onClick={() => void onAddFromSearch(result.url)}>
                    Add to Watchlist
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
