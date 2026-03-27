import { FormEvent, useState } from "react";

import type { AuctionProvider, LiveSyncStatus, ProviderConnectionDiagnostic, WatchlistItem } from "../../types";
import { AsyncStatus } from "../shared/AsyncStatus";
import { LotThumbnail } from "../shared/LotThumbnail";
import { buildResourceReliability } from "../shared/resourceReliability";
import { LotGalleryModal } from "./LotGalleryModal";

type Props = {
  items: WatchlistItem[];
  isLoading: boolean;
  loadError: string | null;
  isAddingLot: boolean;
  refreshingItemId: string | null;
  removingItemId: string | null;
  isBrowserOffline: boolean;
  liveSyncStatus: LiveSyncStatus | null;
  copartConnectionDiagnostic: ProviderConnectionDiagnostic | null;
  iaaiConnectionDiagnostic: ProviderConnectionDiagnostic | null;
  onRetry: () => Promise<void>;
  onAddByIdentifier: (provider: AuctionProvider, lotNumber: string) => Promise<void>;
  onRefreshItem: (id: string) => Promise<WatchlistItem>;
  onRemove: (id: string) => Promise<void>;
};

export function WatchlistPanel({
  items,
  isLoading,
  loadError,
  isAddingLot,
  refreshingItemId,
  removingItemId,
  isBrowserOffline,
  liveSyncStatus,
  copartConnectionDiagnostic,
  iaaiConnectionDiagnostic,
  onRetry,
  onAddByIdentifier,
  onRefreshItem,
  onRemove,
}: Props) {
  const [manualProvider, setManualProvider] = useState<AuctionProvider>("copart");
  const [lotNumber, setLotNumber] = useState("");
  const [selectedLot, setSelectedLot] = useState<WatchlistItem | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [expandedItems, setExpandedItems] = useState<Record<string, boolean>>({});
  const selectedDiagnostic = manualProvider === "iaai" ? iaaiConnectionDiagnostic : copartConnectionDiagnostic;
  const isManualActionBlocked = Boolean(selectedDiagnostic && selectedDiagnostic.status !== "ready");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!lotNumber.trim() || isAddingLot || isManualActionBlocked) {
      return;
    }
    setActionError(null);
    setActionNotice(null);
    try {
      await onAddByIdentifier(manualProvider, lotNumber.trim());
      setActionNotice(`${manualProvider === "iaai" ? "IAAI" : "Copart"} lot ${lotNumber.trim()} added to tracked lots.`);
      setLotNumber("");
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Couldn't add this lot.");
    }
  }

  async function handleRemove(id: string) {
    setActionError(null);
    setActionNotice(null);
    try {
      await onRemove(id);
      setActionNotice("Removed from tracked lots.");
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Couldn't remove this lot.");
    }
  }

  async function handleRefresh(id: string, title: string) {
    setActionError(null);
    setActionNotice(null);
    try {
      await onRefreshItem(id);
      setActionNotice(`Updated ${title}.`);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Couldn't update this lot.");
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

  function getReliabilityState(
    item: WatchlistItem,
  ): { label: string; tone: "live" | "cached" | "warning" | "danger" | "refreshing"; detail: string; needsAttention: boolean } {
    return buildResourceReliability({
      freshness: item.freshness,
      refreshState: item.refresh_state,
      isRefreshing: refreshingItemId === item.id,
      repairPendingDetail: "We're fixing an issue with this vehicle entry.",
      unknownDetail: "We haven't checked this vehicle yet.",
    });
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
      return "You're offline. You can still view saved info, but new updates will wait until you're back online.";
    }
    if (liveSyncStatus?.status === "degraded") {
      return "Live updates are having trouble right now. You can still view saved info, but checking for new changes may fail.";
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
      {isManualActionBlocked && selectedDiagnostic ? (
        <AsyncStatus tone="neutral" compact message={selectedDiagnostic.message} className="panel-status" />
      ) : null}
      {loadError ? (
        <AsyncStatus
          tone="error"
          title="Couldn't load tracked lots"
          message={loadError}
          action={
            <button type="button" className="ghost-button" onClick={() => void onRetry()}>
              Try again
            </button>
          }
          className="panel-status"
        />
      ) : null}
      {actionError ? (
        <AsyncStatus tone="error" title="Couldn't update tracked lots" message={actionError} className="panel-status" />
      ) : null}
      {actionNotice ? <AsyncStatus tone="success" compact message={actionNotice} className="panel-status" /> : null}
      <form className="watchlist-form" onSubmit={handleSubmit} aria-busy={isAddingLot}>
        <label className="watchlist-form__field">
          Auction site
          <select value={manualProvider} onChange={(event) => setManualProvider(event.target.value as AuctionProvider)}>
            <option value="copart">Copart</option>
            <option value="iaai">IAAI</option>
          </select>
        </label>
        <label className="watchlist-form__field">
          Lot or stock number
          <input
            value={lotNumber}
            onChange={(event) => setLotNumber(event.target.value)}
            inputMode={manualProvider === "copart" ? "numeric" : "text"}
            pattern={manualProvider === "copart" ? "[0-9]*" : undefined}
            autoComplete="off"
            autoCapitalize="off"
            autoCorrect="off"
            spellCheck={false}
            placeholder={manualProvider === "copart" ? "99251295" : "STK-44 or item ID"}
            disabled={isManualActionBlocked}
          />
        </label>
        <button type="submit" disabled={!lotNumber.trim() || isAddingLot || isManualActionBlocked} aria-busy={isAddingLot}>
          {isAddingLot ? "Adding..." : isManualActionBlocked ? "Reconnect account" : "Add Lot"}
        </button>
      </form>
      {isAddingLot ? (
        <AsyncStatus
          compact
          progress="bar"
          title="Adding lot"
          message="We'll keep your current list visible while we load the details."
          className="panel-status"
        />
      ) : null}
      {isLoading && items.length === 0 ? (
        <AsyncStatus
          progress="spinner"
          title="Loading tracked lots"
          message="Getting your saved vehicle details ready."
          className="panel-status"
        />
      ) : null}
      {!isLoading && items.length === 0 && !loadError ? (
        <p className="muted">You haven't added any lots yet.</p>
      ) : (
        <div className="result-list watchlist-list">
          {items.map((item) => {
            const urgency = getSaleUrgency(item.sale_date);
            const isExpanded = expandedItems[item.id] ?? false;
            const reliability = getReliabilityState(item);

            return (
              <article
                key={item.id}
                className={`result-card result-card--media watchlist-card${item.has_unseen_update ? " watchlist-card--updated" : ""}${urgency ? ` watchlist-card--${urgency.tone}` : ""}${reliability.needsAttention ? " watchlist-card--attention" : ""}`}
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
                        {item.url ? (
                          <a
                            className="watchlist-card__lot-link"
                            href={item.url}
                            target="_blank"
                            rel="noreferrer"
                            aria-label={`Open ${item.auction_label} lot ${item.lot_number}`}
                          >
                            Lot {item.lot_number}
                          </a>
                        ) : (
                          <span className="watchlist-card__lot-link">Lot {item.lot_number}</span>
                        )}
                        <span className="status-pill">{item.auction_label}</span>
                        <span className="status-pill">{item.raw_status || item.status}</span>
                      </div>
                    </div>
                    <div className="watchlist-card__header-badges">
                      {item.has_unseen_update ? <span className="watchlist-card__update-badge">Changed</span> : null}
                    </div>
                  </div>
                  <dl className="watchlist-card__signals">
                    <div className="watchlist-card__signal">
                      <dt className="detail-label">Current bid</dt>
                      <dd className="detail-value">{formatMoney(item.current_bid, item.currency)}</dd>
                    </div>
                    <div className="watchlist-card__signal">
                      <dt className="detail-label">Odometer</dt>
                      <dd className="detail-value">{formatDetailValue(item.odometer)}</dd>
                    </div>
                  </dl>
                  <div className="watchlist-card__reliability">
                    <span className={`status-pill status-pill--${reliability.tone}`}>{reliability.label}</span>
                    <p className="watchlist-card__reliability-copy">{reliability.detail}</p>
                  </div>
                  {item.connection_diagnostic && item.connection_diagnostic.status !== "ready" ? (
                    <AsyncStatus tone="neutral" compact message={item.connection_diagnostic.message} className="panel-status" />
                  ) : null}
                  {item.has_unseen_update ? (
                    <div className="watchlist-card__update-callout" role="status" aria-live="polite">
                      <p className="watchlist-card__update-summary">{formatLatestChangeSummary(item).join(" · ")}</p>
                      {item.latest_change_at ? (
                        <p className="watchlist-card__update-meta">Found {formatLastChecked(item.latest_change_at)}</p>
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
                    onClick={() => void handleRefresh(item.id, item.title)}
                    disabled={
                      refreshingItemId === item.id ||
                      Boolean(item.connection_diagnostic && item.connection_diagnostic.status !== "ready")
                    }
                    aria-busy={refreshingItemId === item.id}
                  >
                    {refreshingItemId === item.id
                      ? "Updating..."
                      : item.connection_diagnostic && item.connection_diagnostic.status !== "ready"
                        ? `Reconnect ${item.auction_label}`
                        : "Check now"}
                  </button>
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
