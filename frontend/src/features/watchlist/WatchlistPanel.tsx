import { FormEvent, useState } from "react";

import type { LiveSyncStatus, WatchlistItem } from "../../types";
import { AsyncStatus } from "../shared/AsyncStatus";
import { LotThumbnail } from "../shared/LotThumbnail";
import { LotGalleryModal } from "./LotGalleryModal";

type Props = {
  items: WatchlistItem[];
  isLoading: boolean;
  loadError: string | null;
  isAddingLot: boolean;
  removingItemId: string | null;
  isBrowserOffline: boolean;
  liveSyncStatus: LiveSyncStatus | null;
  onRetry: () => Promise<void>;
  onAddByLotNumber: (lotNumber: string) => Promise<void>;
  onRemove: (id: string) => Promise<void>;
};

export function WatchlistPanel({
  items,
  isLoading,
  loadError,
  isAddingLot,
  removingItemId,
  isBrowserOffline,
  liveSyncStatus,
  onRetry,
  onAddByLotNumber,
  onRemove,
}: Props) {
  const [lotNumber, setLotNumber] = useState("");
  const [selectedLot, setSelectedLot] = useState<WatchlistItem | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!lotNumber.trim() || isAddingLot) {
      return;
    }
    setActionError(null);
    setActionNotice(null);
    try {
      await onAddByLotNumber(lotNumber.trim());
      setActionNotice(`Tracked lot ${lotNumber.trim()} added.`);
      setLotNumber("");
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Could not add lot.");
    }
  }

  async function handleRemove(id: string) {
    setActionError(null);
    setActionNotice(null);
    try {
      await onRemove(id);
      setActionNotice("Tracked lot removed.");
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Could not remove lot.");
    }
  }

  function formatDetailValue(value: string | null | undefined): string {
    return value && value.trim() ? value : "—";
  }

  function formatHasKey(value: boolean | null): string {
    if (value === true) {
      return "Yes";
    }
    if (value === false) {
      return "No";
    }
    return "—";
  }

  function formatMoney(value: number | null, currency: string): string {
    if (value === null) {
      return "—";
    }
    const digits = Number.isInteger(value) ? 0 : 2;
    return `${new Intl.NumberFormat("en-US", {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    }).format(value)} ${currency}`;
  }

  function formatLocalAuctionStart(value: string | null): string {
    if (!value) {
      return "—";
    }
    return new Intl.DateTimeFormat(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(value));
  }

  function formatLastChecked(value: string): string {
    return new Intl.DateTimeFormat(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(value));
  }

  function getTrackedLotDetails(item: WatchlistItem) {
    return [
      { label: "Status", value: formatDetailValue(item.raw_status), emphasis: true },
      { label: "Last checked", value: formatLastChecked(item.last_checked_at) },
      { label: "Odometer", value: formatDetailValue(item.odometer) },
      { label: "Primary damage", value: formatDetailValue(item.primary_damage) },
      { label: "Retail", value: formatMoney(item.estimated_retail_value, item.currency) },
      { label: "Has Key", value: formatHasKey(item.has_key) },
      { label: "Drivetrain", value: formatDetailValue(item.drivetrain) },
      { label: "Highlights", value: item.highlights.length > 0 ? item.highlights.join(" · ") : "—", full: true },
      { label: "Vin", value: formatDetailValue(item.vin), full: true },
    ];
  }

  function getTrackedLotSummary(item: WatchlistItem) {
    return [
      {
        label: "Lot",
        value: (
          <a
            className="watchlist-card__lot-link"
            href={item.url}
            target="_blank"
            rel="noreferrer"
            aria-label={`Open Copart lot ${item.lot_number}`}
          >
            {item.lot_number}
          </a>
        ),
      },
      {
        label: "Bid",
        value: formatMoney(item.current_bid, item.currency),
      },
      {
        label: "Sale",
        value: formatLocalAuctionStart(item.sale_date),
      },
    ];
  }

  function getWatchlistContextMessage(): string | null {
    if (isBrowserOffline) {
      return "This device is offline. Live lot updates and new additions will resume after reconnecting.";
    }
    if (liveSyncStatus?.status === "degraded") {
      return "Live Copart sync is unavailable. Existing tracked data stays visible while refresh-dependent actions may fail.";
    }
    return null;
  }

  const contextMessage = getWatchlistContextMessage();

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Watchlist</p>
          <h2>Tracked Lots</h2>
        </div>
      </div>
      {contextMessage ? <AsyncStatus compact message={contextMessage} className="panel-status" /> : null}
      {loadError ? (
        <AsyncStatus
          tone="error"
          title="Tracked lots unavailable"
          message={loadError}
          action={
            <button type="button" className="ghost-button" onClick={() => void onRetry()}>
              Retry watchlist
            </button>
          }
          className="panel-status"
        />
      ) : null}
      {actionError ? (
        <AsyncStatus tone="error" title="Watchlist action failed" message={actionError} className="panel-status" />
      ) : null}
      {actionNotice ? <AsyncStatus tone="success" compact message={actionNotice} className="panel-status" /> : null}
      <form className="search-grid watchlist-form" onSubmit={handleSubmit} aria-busy={isAddingLot}>
        <label>
          Add by Lot Number
          <input
            value={lotNumber}
            onChange={(event) => setLotNumber(event.target.value)}
            placeholder="99251295"
          />
        </label>
        <button type="submit" disabled={!lotNumber.trim() || isAddingLot} aria-busy={isAddingLot}>
          {isAddingLot ? "Adding..." : "Add Lot"}
        </button>
      </form>
      {isAddingLot ? (
        <AsyncStatus
          compact
          progress="bar"
          title="Adding tracked lot"
          message="Current watchlist items stay visible while fresh lot details load."
          className="panel-status"
        />
      ) : null}
      {isLoading && items.length === 0 ? (
        <AsyncStatus
          progress="spinner"
          title="Loading tracked lots"
          message="Saved lot details and freshness metadata are loading."
          className="panel-status"
        />
      ) : null}
      {!isLoading && items.length === 0 && !loadError ? (
        <p className="muted">No lots tracked yet.</p>
      ) : (
        <div className="result-list watchlist-list">
          {items.map((item) => (
            <article key={item.id} className="result-card result-card--media watchlist-card">
              <LotThumbnail
                title={item.title}
                thumbnailUrl={item.thumbnail_url}
                onClick={item.image_urls.length > 0 ? () => setSelectedLot(item) : undefined}
              />
              <div className="result-copy watchlist-card__body">
                <div className="watchlist-card__header">
                  <strong>{item.title}</strong>
                  <span className="status-pill">{item.status}</span>
                </div>
                <dl className="watchlist-card__summary">
                  {getTrackedLotSummary(item).map((detail) => (
                    <div key={detail.label} className="watchlist-card__detail detail-item">
                      <dt className="watchlist-card__detail-label detail-label">{detail.label}:</dt>
                      <dd className="watchlist-card__detail-value detail-value">{detail.value}</dd>
                    </div>
                  ))}
                </dl>
                <dl className="watchlist-card__details">
                  {getTrackedLotDetails(item).map((detail) => (
                    <div
                      key={detail.label}
                      className={`watchlist-card__detail detail-item${detail.full ? " watchlist-card__detail--full" : ""}`}
                    >
                      <dt className="watchlist-card__detail-label detail-label">{detail.label}:</dt>
                      <dd
                        className={`watchlist-card__detail-value detail-value${detail.emphasis ? " watchlist-card__detail-value--emphasis" : ""}`}
                      >
                        {detail.value}
                      </dd>
                    </div>
                  ))}
                </dl>
              </div>
              <div className="watchlist-card__actions">
                <button
                  type="button"
                  className="ghost-button"
                  onClick={() => void handleRemove(item.id)}
                  disabled={removingItemId === item.id}
                  aria-busy={removingItemId === item.id}
                >
                  {removingItemId === item.id ? "Removing..." : "Remove"}
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
      <LotGalleryModal
        title={selectedLot?.title ?? ""}
        imageUrls={selectedLot?.image_urls ?? []}
        isOpen={selectedLot !== null}
        onClose={() => setSelectedLot(null)}
      />
    </section>
  );
}
