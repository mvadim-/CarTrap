import { FormEvent, useEffect, useState } from "react";

import type {
  AuctionProvider,
  LiveSyncStatus,
  ProviderConnectionDiagnostic,
  WatchlistHistoryEntry,
  WatchlistHistoryResponse,
  WatchlistItem,
} from "../../types";
import { AsyncStatus } from "../shared/AsyncStatus";
import { AuctionProviderBadge, getAuctionProviderLabel } from "../shared/AuctionProviderBadge";
import { LotThumbnail } from "../shared/LotThumbnail";
import { buildResourceReliability } from "../shared/resourceReliability";
import { LotChangeHistoryModal } from "./LotChangeHistoryModal";
import { LotGalleryModal } from "./LotGalleryModal";
import { TrackLotModal } from "./TrackLotModal";

type Props = {
  isMobileLayout: boolean;
  items: WatchlistItem[];
  isLoading: boolean;
  loadError: string | null;
  isAddingLot: boolean;
  refreshingItemId: string | null;
  acknowledgingItemId: string | null;
  removingItemId: string | null;
  isBrowserOffline: boolean;
  liveSyncStatus: LiveSyncStatus | null;
  copartConnectionDiagnostic: ProviderConnectionDiagnostic | null;
  iaaiConnectionDiagnostic: ProviderConnectionDiagnostic | null;
  onRetry: () => Promise<void>;
  onAddByIdentifier: (provider: AuctionProvider, lotNumber: string) => Promise<void>;
  onRefreshItem: (id: string) => Promise<WatchlistItem>;
  onLoadItemHistory: (id: string) => Promise<WatchlistHistoryResponse>;
  onAcknowledgeItemUpdate: (id: string) => Promise<WatchlistItem>;
  onRemove: (id: string) => Promise<void>;
};

export function WatchlistPanel({
  isMobileLayout,
  items,
  isLoading,
  loadError,
  isAddingLot,
  refreshingItemId,
  acknowledgingItemId,
  removingItemId,
  isBrowserOffline,
  liveSyncStatus,
  copartConnectionDiagnostic,
  iaaiConnectionDiagnostic,
  onRetry,
  onAddByIdentifier,
  onRefreshItem,
  onLoadItemHistory,
  onAcknowledgeItemUpdate,
  onRemove,
}: Props) {
  const [manualProvider, setManualProvider] = useState<AuctionProvider>("copart");
  const [lotNumber, setLotNumber] = useState("");
  const [selectedLot, setSelectedLot] = useState<WatchlistItem | null>(null);
  const [historyLot, setHistoryLot] = useState<WatchlistItem | null>(null);
  const [isTrackLotModalOpen, setIsTrackLotModalOpen] = useState(false);
  const [historyEntries, setHistoryEntries] = useState<WatchlistHistoryEntry[]>([]);
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [expandedItems, setExpandedItems] = useState<Record<string, boolean>>({});
  const [isSectionCollapsed, setIsSectionCollapsed] = useState(false);
  const selectedDiagnostic = manualProvider === "iaai" ? iaaiConnectionDiagnostic : copartConnectionDiagnostic;
  const isManualActionBlocked = Boolean(selectedDiagnostic && selectedDiagnostic.status !== "ready");
  const isSectionContentVisible = !isMobileLayout || !isSectionCollapsed;
  const manualProviderLabel = getAuctionProviderLabel(manualProvider);

  useEffect(() => {
    if (!isMobileLayout) {
      setIsSectionCollapsed(false);
    }
  }, [isMobileLayout]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!lotNumber.trim() || isAddingLot || isManualActionBlocked) {
      return;
    }
    setActionError(null);
    setActionNotice(null);
    try {
      await onAddByIdentifier(manualProvider, lotNumber.trim());
      setActionNotice(`${manualProviderLabel} lot ${lotNumber.trim()} added to tracked lots.`);
      setLotNumber("");
      setIsTrackLotModalOpen(false);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Couldn't add this lot.");
    }
  }

  function handleOpenTrackLotModal() {
    setActionError(null);
    setIsTrackLotModalOpen(true);
  }

  function handleCloseTrackLotModal() {
    setIsTrackLotModalOpen(false);
    setActionError(null);
    setLotNumber("");
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

  async function handleAcknowledgeUpdate(id: string) {
    setActionError(null);
    setActionNotice(null);
    try {
      await onAcknowledgeItemUpdate(id);
      setActionNotice("Update marked as seen.");
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Couldn't mark this update as seen.");
    }
  }

  async function handleOpenHistory(item: WatchlistItem) {
    setHistoryLot(item);
    setHistoryEntries([]);
    setHistoryError(null);
    setIsHistoryLoading(true);
    try {
      const response = await onLoadItemHistory(item.id);
      setHistoryEntries(response.entries);
    } catch (error) {
      setHistoryError(error instanceof Error ? error.message : "Couldn't load change history.");
    } finally {
      setIsHistoryLoading(false);
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

  function hasLatestChangeSummary(item: WatchlistItem): boolean {
    return Object.keys(item.latest_changes).length > 0;
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
    <>
      <section className="panel panel--watchlist panel--operational">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Watchlist</p>
            <h2>Tracked Lots</h2>
            <p className="muted panel-header__lede">
              Track a Copart or IAAI lot to watch bid, status, and sale-time changes.
            </p>
          </div>
          <div className="panel-header__actions">
            <button type="button" className="ghost-button" onClick={handleOpenTrackLotModal} disabled={isManualActionBlocked}>
              Track Lot
            </button>
            {isMobileLayout ? (
              <button
                type="button"
                className="ghost-button ghost-button--quiet panel-collapse-toggle"
                aria-controls="tracked-lots-panel-content"
                aria-expanded={isSectionContentVisible}
                aria-label={`${isSectionContentVisible ? "Collapse" : "Expand"} Tracked Lots`}
                onClick={() => setIsSectionCollapsed((current) => !current)}
              >
                {isSectionContentVisible ? "Hide section" : "Show section"}
              </button>
            ) : null}
          </div>
        </div>
        {isSectionContentVisible ? (
          <div id="tracked-lots-panel-content">
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
            {!isTrackLotModalOpen && actionError ? (
              <AsyncStatus tone="error" title="Couldn't update tracked lots" message={actionError} className="panel-status" />
            ) : null}
            {actionNotice ? <AsyncStatus tone="success" compact message={actionNotice} className="panel-status" /> : null}
            {isLoading && items.length === 0 ? (
              <AsyncStatus
                progress="spinner"
                title="Loading tracked lots"
                message="Getting your saved vehicle details ready."
                className="panel-status"
              />
            ) : null}
            {!isLoading && items.length === 0 && !loadError ? (
              <div className="saved-search-empty-state watchlist-empty-state">
                <p className="saved-search-empty-state__title">You haven't added any lots yet.</p>
                <p className="muted">Track a lot when you want auction changes to stay one tap away.</p>
                <button type="button" onClick={handleOpenTrackLotModal} disabled={isManualActionBlocked}>
                  Track your first lot
                </button>
              </div>
            ) : (
              <div className="result-list watchlist-list">
                {items.map((item) => {
                  const urgency = getSaleUrgency(item.sale_date);
                  const isExpanded = expandedItems[item.id] ?? false;
                  const reliability = getReliabilityState(item);
                const hasChangeSummary = hasLatestChangeSummary(item);
                const isUnreadChange = item.has_unseen_update && hasChangeSummary;

                return (
                  <article
                    key={item.id}
                    className={`result-card result-card--media watchlist-card${isUnreadChange ? " watchlist-card--updated" : ""}${urgency ? ` watchlist-card--${urgency.tone}` : ""}${reliability.needsAttention ? " watchlist-card--attention" : ""}`}
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
                            <AuctionProviderBadge provider={item.provider} label={item.auction_label} />
                            <span className="status-pill">{item.raw_status || item.status}</span>
                          </div>
                        </div>
                        <div className="watchlist-card__header-badges">
                          {isUnreadChange ? <span className="watchlist-card__update-badge">Changed</span> : null}
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
                      {hasChangeSummary ? (
                        <div
                          className={`watchlist-card__update-callout${isUnreadChange ? "" : " watchlist-card__update-callout--seen"}`}
                          role="status"
                          aria-live="polite"
                        >
                          <p className="watchlist-card__update-kicker">{isUnreadChange ? "New change" : "Last change"}</p>
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
                      {isUnreadChange ? (
                        <button
                          type="button"
                          className="ghost-button ghost-button--quiet"
                          onClick={() => void handleAcknowledgeUpdate(item.id)}
                          disabled={acknowledgingItemId === item.id}
                          aria-busy={acknowledgingItemId === item.id}
                        >
                          {acknowledgingItemId === item.id ? "Saving..." : "Mark seen"}
                        </button>
                      ) : null}
                      <button
                        type="button"
                        className="ghost-button ghost-button--quiet"
                        onClick={() => void handleRefresh(item.id, item.title)}
                        disabled={
                          refreshingItemId === item.id ||
                          acknowledgingItemId === item.id ||
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
                      <button type="button" className="ghost-button ghost-button--quiet" onClick={() => void handleOpenHistory(item)}>
                        Change history
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
          </div>
        ) : null}
      </section>
      <LotGalleryModal
        title={selectedLot?.title ?? ""}
        imageUrls={selectedLot?.image_urls ?? []}
        isOpen={selectedLot !== null}
        onClose={() => setSelectedLot(null)}
      />
      <LotChangeHistoryModal
        title={historyLot?.title ?? ""}
        isOpen={historyLot !== null}
        isLoading={isHistoryLoading}
        error={historyError}
        entries={historyEntries}
        onClose={() => {
          setHistoryLot(null);
          setHistoryEntries([]);
          setHistoryError(null);
          setIsHistoryLoading(false);
        }}
      />
      <TrackLotModal
        isOpen={isTrackLotModalOpen}
        manualProvider={manualProvider}
        lotNumber={lotNumber}
        isAddingLot={isAddingLot}
        isManualActionBlocked={isManualActionBlocked}
        selectedDiagnostic={selectedDiagnostic}
        actionError={actionError}
        onClose={handleCloseTrackLotModal}
        onManualProviderChange={setManualProvider}
        onLotNumberChange={setLotNumber}
        onSubmit={handleSubmit}
      />
    </>
  );
}
