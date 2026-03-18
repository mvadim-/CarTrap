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
  const [expandedItems, setExpandedItems] = useState<Record<string, boolean>>({});

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

  function getSaleUrgency(value: string | null): { label: string; tone: "live" | "soon" | "today" } | null {
    if (!value) {
      return null;
    }
    const saleDate = new Date(value);
    const diffMs = saleDate.getTime() - Date.now();
    if (diffMs <= 0) {
      return { label: "Auction live", tone: "live" };
    }
    if (diffMs <= 120 * 60 * 1000) {
      return { label: "Sale soon", tone: "soon" };
    }
    const now = new Date();
    const isSameDay =
      saleDate.getFullYear() === now.getFullYear() &&
      saleDate.getMonth() === now.getMonth() &&
      saleDate.getDate() === now.getDate();
    if (isSameDay) {
      return { label: "Today", tone: "today" };
    }
    return null;
  }

  function formatChangeValue(item: WatchlistItem, field: string, value: unknown): string {
    if (value === null || value === undefined || value === "") {
      return "none";
    }
    if ((field === "current_bid" || field === "buy_now_price") && typeof value === "number") {
      return formatMoney(value, item.currency);
    }
    if (field === "sale_date" && typeof value === "string") {
      return formatLocalAuctionStart(value);
    }
    return String(value);
  }

  function formatLatestChangeSummary(item: WatchlistItem): string[] {
    const changes = item.latest_changes;
    const hasRawStatus = "raw_status" in changes;
    const orderedFields = [
      "raw_status",
      "status",
      "current_bid",
      "buy_now_price",
      "sale_date",
      ...Object.keys(changes),
    ];
    const seen = new Set<string>();
    const summaries: string[] = [];
    for (const field of orderedFields) {
      if (seen.has(field) || !(field in changes)) {
        continue;
      }
      seen.add(field);
      if (field === "status" && hasRawStatus) {
        continue;
      }
      const change = changes[field];
      if (!change) {
        continue;
      }
      const label =
        field === "raw_status"
          ? "Status"
          : field === "current_bid"
            ? "Bid"
            : field === "buy_now_price"
              ? "Buy now"
              : field === "sale_date"
                ? "Sale"
                : field.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
      summaries.push(
        `${label}: ${formatChangeValue(item, field, change.before)} -> ${formatChangeValue(item, field, change.after)}`,
      );
    }
    return summaries;
  }

  function getTrackedLotDetails(item: WatchlistItem) {
    return [
      { label: "Status", value: formatDetailValue(item.raw_status), emphasis: true },
      { label: "Primary damage", value: formatDetailValue(item.primary_damage) },
      { label: "Retail", value: formatMoney(item.estimated_retail_value, item.currency) },
      { label: "Has Key", value: formatHasKey(item.has_key) },
      { label: "Drivetrain", value: formatDetailValue(item.drivetrain) },
      { label: "Buy now", value: formatMoney(item.buy_now_price, item.currency) },
      { label: "Highlights", value: item.highlights.length > 0 ? item.highlights.join(" · ") : "—", full: true },
      { label: "Vin", value: formatDetailValue(item.vin), full: true },
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
    <section className="panel panel--watchlist panel--operational">
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
      <form className="watchlist-form" onSubmit={handleSubmit} aria-busy={isAddingLot}>
        <label className="watchlist-form__field">
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
          {items.map((item) => {
            const urgency = getSaleUrgency(item.sale_date);
            const isExpanded = expandedItems[item.id] ?? false;

            return (
              <article
                key={item.id}
                className={`result-card result-card--media watchlist-card${item.has_unseen_update ? " watchlist-card--updated" : ""}${urgency ? ` watchlist-card--${urgency.tone}` : ""}`}
              >
                <LotThumbnail
                  title={item.title}
                  thumbnailUrl={item.thumbnail_url}
                  variant="watchlist"
                  onClick={item.image_urls.length > 0 ? () => setSelectedLot(item) : undefined}
                />
                <div className="result-copy watchlist-card__body">
                  <div className="watchlist-card__header">
                    <div className="watchlist-card__title-block">
                      <div className="watchlist-card__sale-row">
                        {urgency ? (
                          <span className={`watchlist-card__urgency-badge watchlist-card__urgency-badge--${urgency.tone}`}>
                            {urgency.label}
                          </span>
                        ) : null}
                        <p className="watchlist-card__sale-time">Sale {formatLocalAuctionStart(item.sale_date)}</p>
                      </div>
                      <strong>{item.title}</strong>
                      <div className="watchlist-card__meta-row">
                        <a
                          className="watchlist-card__lot-link"
                          href={item.url}
                          target="_blank"
                          rel="noreferrer"
                          aria-label={`Open Copart lot ${item.lot_number}`}
                        >
                          Lot {item.lot_number}
                        </a>
                        <span className="status-pill">{item.raw_status || item.status}</span>
                      </div>
                    </div>
                    <div className="watchlist-card__header-badges">
                      {item.has_unseen_update ? <span className="watchlist-card__update-badge">Updated</span> : null}
                    </div>
                  </div>
                  <dl className="watchlist-card__signals">
                    <div className="watchlist-card__signal">
                      <dt className="detail-label">Current bid</dt>
                      <dd className="detail-value">{formatMoney(item.current_bid, item.currency)}</dd>
                    </div>
                    <div className="watchlist-card__signal">
                      <dt className="detail-label">Last checked</dt>
                      <dd className="detail-value">{formatLastChecked(item.last_checked_at)}</dd>
                    </div>
                    <div className="watchlist-card__signal">
                      <dt className="detail-label">Odometer</dt>
                      <dd className="detail-value">{formatDetailValue(item.odometer)}</dd>
                    </div>
                  </dl>
                  {item.has_unseen_update ? (
                    <div className="watchlist-card__update-callout" role="status" aria-live="polite">
                      <p className="watchlist-card__update-summary">{formatLatestChangeSummary(item).join(" · ")}</p>
                      {item.latest_change_at ? (
                        <p className="watchlist-card__update-meta">Detected {formatLastChecked(item.latest_change_at)}</p>
                      ) : null}
                    </div>
                  ) : null}
                  {isExpanded ? (
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
                  ) : null}
                </div>
                <div className="watchlist-card__actions">
                  <button
                    type="button"
                    className="ghost-button ghost-button--quiet"
                    aria-expanded={isExpanded}
                    onClick={() =>
                      setExpandedItems((current) => ({
                        ...current,
                        [item.id]: !isExpanded,
                      }))
                    }
                  >
                    {isExpanded ? "Hide details" : "Show details"}
                  </button>
                  <button
                    type="button"
                    className="ghost-button ghost-button--quiet"
                    onClick={() => void handleRemove(item.id)}
                    disabled={removingItemId === item.id}
                    aria-busy={removingItemId === item.id}
                  >
                    {removingItemId === item.id ? "Removing..." : "Remove"}
                  </button>
                </div>
              </article>
            );
          })}
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
