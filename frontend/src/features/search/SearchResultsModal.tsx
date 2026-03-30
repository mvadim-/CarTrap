import { useEffect, useRef, type UIEvent } from "react";
import { createPortal } from "react-dom";

import type { FreshnessEnvelope, ProviderConnectionDiagnostic, RefreshState, SearchResult } from "../../types";
import { AsyncStatus } from "../shared/AsyncStatus";
import { AuctionProviderBadge } from "../shared/AuctionProviderBadge";
import { LotThumbnail } from "../shared/LotThumbnail";
import { shouldUseMobileFullscreen } from "../shared/mobileFullscreen";
import { buildResourceReliability } from "../shared/resourceReliability";
import { useBodyScrollLock } from "../shared/useBodyScrollLock";

type Props = {
  isOpen: boolean;
  title: string;
  results: SearchResult[];
  totalResults: number;
  onClose: () => void;
  onAddFromSearch: (result: SearchResult) => Promise<void>;
  onSaveSearch: () => Promise<void>;
  canSave: boolean;
  isSavingSearch?: boolean;
  addingFromSearchLotUrl?: string | null;
  trackedLotKeys?: string[];
  canRefreshLive?: boolean;
  onRefreshLive?: () => Promise<void>;
  isRefreshingLive?: boolean;
  lastSyncedAt?: string | null;
  freshness?: FreshnessEnvelope | null;
  refreshState?: RefreshState | null;
  connectionDiagnostics?: ProviderConnectionDiagnostic[];
  refreshError?: string | null;
  statusMessage?: string | null;
  mobileFullscreen?: boolean;
};

const FALLBACK_MOBILE_COLLAPSIBLE_HEIGHT = 220;

function formatMoney(value: number | null | undefined, currency: string) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return null;
  }

  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(value);
}

function formatStatusLabel(status: string | null | undefined) {
  if (!status) {
    return "Status unknown";
  }

  return status
    .replace(/_/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function getReliabilityBadge(
  freshness: FreshnessEnvelope | null,
  refreshState: RefreshState | null,
  isRefreshingLive: boolean,
): { label: string; tone: "live" | "cached" | "warning" | "danger" | "refreshing"; detail: string } | null {
  if (!freshness && !refreshState) {
    return null;
  }

  return buildResourceReliability({
    freshness,
    refreshState,
    isRefreshing: isRefreshingLive,
    repairPendingDetail: "We're fixing an issue with this saved search.",
    unknownDetail: "We haven't checked this saved search yet.",
  });
}

function formatRelativeSaleTime(saleDate: string | null, isLive: boolean) {
  if (!saleDate) {
    return isLive ? "Live now" : "Sale date TBD";
  }

  const diffMinutes = Math.max(1, Math.round(Math.abs(new Date(saleDate).getTime() - Date.now()) / 60000));
  const days = Math.floor(diffMinutes / (60 * 24));
  const hours = Math.floor((diffMinutes % (60 * 24)) / 60);
  const minutes = diffMinutes % 60;
  const parts: string[] = [];

  if (days > 0) {
    parts.push(`${days}d`);
  }
  if (hours > 0) {
    parts.push(`${hours}h`);
  }
  if (minutes > 0 && parts.length < 2) {
    parts.push(`${minutes}m`);
  }
  if (parts.length === 0) {
    parts.push("1m");
  }

  return isLive ? `${parts.join(" ")} live` : parts.join(" ");
}

function getMarketSignal(result: SearchResult) {
  const isLive = result.status === "live";
  const currentBid = formatMoney(result.current_bid, result.currency);
  const buyNowPrice =
    typeof result.buy_now_price === "number" && result.buy_now_price > 0
      ? formatMoney(result.buy_now_price, result.currency)
      : null;

  if (isLive) {
    return {
      accent: "live" as const,
      headline: "Auction in progress",
      timer: formatRelativeSaleTime(result.sale_date, true),
      meta: currentBid ? `Current bid ${currentBid}` : null,
    };
  }

  return {
    accent: "default" as const,
    headline: currentBid ?? "Bid pending",
    timer: formatRelativeSaleTime(result.sale_date, false),
    meta: buyNowPrice ? `Buy It Now for ${buyNowPrice}` : formatStatusLabel(result.raw_status ?? result.status),
  };
}

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
  trackedLotKeys = [],
  canRefreshLive = false,
  onRefreshLive,
  isRefreshingLive = false,
  lastSyncedAt = null,
  freshness = null,
  refreshState = null,
  connectionDiagnostics = [],
  refreshError = null,
  statusMessage = null,
  mobileFullscreen = false,
}: Props) {
  const isMobileFullscreen =
    shouldUseMobileFullscreen(mobileFullscreen) ||
    (mobileFullscreen && typeof window !== "undefined" && window.innerWidth <= 640);
  const modalBodyRef = useRef<HTMLDivElement | null>(null);
  const collapsibleRef = useRef<HTMLDivElement | null>(null);
  const collapseFrameRef = useRef<number | null>(null);
  const scheduledCollapseOffsetRef = useRef<number | null>(null);
  const collapseOffsetRef = useRef(0);
  const collapsibleHeightRef = useRef(0);
  useBodyScrollLock(isOpen);

  function resetCollapsibleInlineStyles() {
    const collapsible = collapsibleRef.current;
    if (!collapsible) {
      return;
    }

    collapsible.style.removeProperty("height");
    collapsible.style.removeProperty("--search-results-collapse-progress");
  }

  function getEffectiveCollapsibleHeight() {
    return collapsibleHeightRef.current > 0
      ? collapsibleHeightRef.current
      : isMobileFullscreen
        ? FALLBACK_MOBILE_COLLAPSIBLE_HEIGHT
        : 0;
  }

  function applyCollapseOffset(nextOffset: number) {
    const collapsible = collapsibleRef.current;
    if (!collapsible || !isMobileFullscreen) {
      return;
    }

    const effectiveCollapsibleHeight = getEffectiveCollapsibleHeight();
    const boundedOffset = Math.min(Math.max(nextOffset, 0), effectiveCollapsibleHeight);
    const collapseProgress =
      effectiveCollapsibleHeight > 0 ? Math.min(boundedOffset / effectiveCollapsibleHeight, 1) : 0;

    collapseOffsetRef.current = boundedOffset;
    collapsible.style.height = `${Math.max(effectiveCollapsibleHeight - boundedOffset, 0)}px`;
    collapsible.style.setProperty("--search-results-collapse-progress", collapseProgress.toString());
  }

  function cancelScheduledCollapseFrame() {
    if (collapseFrameRef.current === null) {
      return;
    }

    window.cancelAnimationFrame(collapseFrameRef.current);
    collapseFrameRef.current = null;
  }

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

  useEffect(() => {
    if (!isOpen) {
      collapseOffsetRef.current = 0;
      collapsibleHeightRef.current = 0;
      scheduledCollapseOffsetRef.current = null;
      cancelScheduledCollapseFrame();
      resetCollapsibleInlineStyles();
      return;
    }

    collapseOffsetRef.current = 0;
    scheduledCollapseOffsetRef.current = null;
    cancelScheduledCollapseFrame();
    const modalBody = modalBodyRef.current;
    if (!modalBody) {
      return;
    }

    modalBody.scrollTop = 0;
    if (isMobileFullscreen) {
      applyCollapseOffset(0);
    } else {
      resetCollapsibleInlineStyles();
    }
  }, [isOpen, isMobileFullscreen, results.length, title]);

  useEffect(() => {
    if (!isOpen || !isMobileFullscreen) {
      collapsibleHeightRef.current = 0;
      collapseOffsetRef.current = 0;
      scheduledCollapseOffsetRef.current = null;
      cancelScheduledCollapseFrame();
      resetCollapsibleInlineStyles();
      return;
    }

    const collapsible = collapsibleRef.current;
    if (!collapsible) {
      return;
    }

    const measure = () => {
      const nextHeight = Math.max(collapsible.scrollHeight, collapsible.getBoundingClientRect().height);
      collapsibleHeightRef.current = nextHeight;
      applyCollapseOffset(collapseOffsetRef.current);
    };

    measure();

    if (typeof ResizeObserver === "undefined") {
      return;
    }

    const observer = new ResizeObserver(() => measure());
    observer.observe(collapsible);
    return () => observer.disconnect();
  }, [isOpen, isMobileFullscreen, totalResults, lastSyncedAt, isRefreshingLive, statusMessage, refreshError, title]);

  useEffect(() => {
    return () => {
      cancelScheduledCollapseFrame();
    };
  }, []);

  if (!isOpen) {
    return null;
  }

  function handleBodyScroll(event: UIEvent<HTMLDivElement>) {
    if (!isMobileFullscreen) {
      collapseOffsetRef.current = 0;
      scheduledCollapseOffsetRef.current = null;
      cancelScheduledCollapseFrame();
      resetCollapsibleInlineStyles();
      return;
    }

    const nextOffset = Math.min(event.currentTarget.scrollTop, getEffectiveCollapsibleHeight());
    if (nextOffset === collapseOffsetRef.current && collapseFrameRef.current === null) {
      return;
    }

    scheduledCollapseOffsetRef.current = nextOffset;
    if (collapseFrameRef.current !== null) {
      return;
    }

    collapseFrameRef.current = window.requestAnimationFrame(() => {
      collapseFrameRef.current = null;
      const scheduledOffset = scheduledCollapseOffsetRef.current;
      scheduledCollapseOffsetRef.current = null;
      applyCollapseOffset(scheduledOffset ?? 0);
    });
  }

  const hasStatusPanels = isRefreshingLive || Boolean(statusMessage) || Boolean(refreshError);
  const vehicleCountLabel = `${totalResults} ${totalResults === 1 ? "result" : "results"}`;
  const reliabilityBadge = getReliabilityBadge(freshness, refreshState, isRefreshingLive);
  const blockingDiagnostics = connectionDiagnostics.filter((diagnostic) => diagnostic.status !== "ready");
  const liveRefreshBlocked = connectionDiagnostics.length > 0 && connectionDiagnostics.every((diagnostic) => diagnostic.status !== "ready");

  const modal = (
    <div
      className={`modal-backdrop${isMobileFullscreen ? " modal-backdrop--mobile-screen" : ""}`}
      onClick={onClose}
    >
      <div
        aria-modal="true"
        className={`modal-card search-results-modal${isMobileFullscreen ? " modal-card--mobile-screen" : ""}`}
        role="dialog"
        aria-label="Search results"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="search-results-modal__chrome">
          {isMobileFullscreen ? (
            <>
              <div className="modal-toolbar modal-toolbar--results search-results-modal__topbar">
                <div className="search-results-modal__topbar-copy">
                  <p className="eyebrow">Results</p>
                </div>
                <div className="search-results-modal__actions">
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
                      disabled={isRefreshingLive || liveRefreshBlocked}
                      aria-busy={isRefreshingLive}
                    >
                      {isRefreshingLive ? "Updating..." : liveRefreshBlocked ? "Reconnect account" : "Check for updates"}
                    </button>
                  ) : null}
                  <button type="button" className="ghost-button" onClick={onClose}>
                    Close
                  </button>
                </div>
              </div>
              <div ref={collapsibleRef} className="search-results-modal__collapsible">
                <div className="search-results-modal__collapsible-inner">
                  <div className="search-results-modal__heading search-results-modal__heading--mobile">
                    <h3>{title}</h3>
                  </div>
                  <div className="modal-filter-bar search-results-modal__meta">
                    <span className="muted">
                  {totalResults} {totalResults === 1 ? "result" : "results"} found. These stay on screen until you close this window.
                    </span>
                  </div>
                  {reliabilityBadge ? (
                    <div className="search-results-modal__reliability">
                      <span className={`status-pill status-pill--${reliabilityBadge.tone}`}>{reliabilityBadge.label}</span>
                      <p className="search-results-modal__reliability-copy">{reliabilityBadge.detail}</p>
                    </div>
                  ) : null}
                  {blockingDiagnostics.map((diagnostic) => (
                    <AsyncStatus
                      key={`mobile-${diagnostic.provider}`}
                      tone="neutral"
                      compact
                      message={diagnostic.message}
                      className="panel-status"
                    />
                  ))}
                  {hasStatusPanels ? (
                    <div className="search-results-modal__status-stack">
                      {isRefreshingLive ? (
                        <AsyncStatus
                          compact
                          progress="bar"
                          title="Checking for updates"
                          message="You can keep looking at the current results while we load the latest ones."
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
                          title="Couldn't update results"
                          message={refreshError}
                          className="modal-status"
                        />
                      ) : null}
                    </div>
                  ) : null}
                </div>
              </div>
            </>
          ) : (
            <>
              <div className="modal-header search-results-modal__header">
                <div className="search-results-modal__heading">
                  <p className="eyebrow">Results</p>
                  <h3>{title}</h3>
                </div>
                <div className="modal-toolbar modal-toolbar--results search-results-modal__actions">
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
                      disabled={isRefreshingLive || liveRefreshBlocked}
                      aria-busy={isRefreshingLive}
                    >
                      {isRefreshingLive ? "Updating..." : liveRefreshBlocked ? "Reconnect account" : "Check for updates"}
                    </button>
                  ) : null}
                  <button type="button" className="ghost-button" onClick={onClose}>
                    Close
                  </button>
                </div>
              </div>
              <div className="modal-filter-bar search-results-modal__meta">
                <span className="muted">
                  {totalResults} {totalResults === 1 ? "result" : "results"} found. These stay on screen until you close this window.
                </span>
              </div>
              {reliabilityBadge ? (
                <div className="search-results-modal__reliability">
                  <span className={`status-pill status-pill--${reliabilityBadge.tone}`}>{reliabilityBadge.label}</span>
                  <p className="search-results-modal__reliability-copy">{reliabilityBadge.detail}</p>
                </div>
              ) : null}
              {blockingDiagnostics.map((diagnostic) => (
                <AsyncStatus
                  key={`desktop-${diagnostic.provider}`}
                  tone="neutral"
                  compact
                  message={diagnostic.message}
                  className="panel-status"
                />
              ))}
              {hasStatusPanels ? (
                <div className="search-results-modal__status-stack">
                  {isRefreshingLive ? (
                    <AsyncStatus
                      compact
                      progress="bar"
                      title="Checking for updates"
                      message="You can keep looking at the current results while we load the latest ones."
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
                      title="Couldn't update results"
                      message={refreshError}
                      className="modal-status"
                    />
                  ) : null}
                </div>
              ) : null}
            </>
          )}
        </div>
        <div ref={modalBodyRef} className="modal-body result-list search-results-modal__body" onScroll={handleBodyScroll}>
          {results.length === 0 ? (
            <p className="muted search-results-modal__empty">No results found for this search.</p>
          ) : (
            <>
              <div className="search-results-modal__count" aria-live="polite">
                <strong>{vehicleCountLabel}</strong>
              </div>
              <div className="search-results-modal__list">
                {results.map((result) => {
                  const marketSignal = getMarketSignal(result);
                  const trackingKey = result.lot_key || result.provider_lot_id || result.url || result.lot_number;
                  const isAdding = addingFromSearchLotUrl === trackingKey;
                  const isTracked = trackedLotKeys.includes(result.lot_key);

                  return (
                    <article key={result.lot_key} className="search-result-row">
                      <LotThumbnail title={result.title} thumbnailUrl={result.thumbnail_url} />
                      <div className="search-result-row__body">
                        <div className="search-result-row__title-line">
                          {result.url ? (
                            <a
                              className="search-result-row__title-link"
                              href={result.url}
                              target="_blank"
                              rel="noreferrer"
                              aria-label={`Open ${result.auction_label} lot ${result.lot_number}`}
                              title={`Open ${result.auction_label} lot page`}
                            >
                              <strong className="search-result-row__title">{result.title}</strong>
                            </a>
                          ) : (
                            <strong className="search-result-row__title">{result.title}</strong>
                          )}
                          {result.is_new ? <span className="new-badge">NEW</span> : null}
                        </div>
                        <div className="search-result-row__meta">
                          <AuctionProviderBadge provider={result.provider} label={result.auction_label} />
                          <span>Lot#: {result.lot_number}</span>
                        </div>
                        <p className="search-result-row__location">{result.location ?? "Location not listed"}</p>
                        <p className="search-result-row__odometer">Odometer: {result.odometer?.trim() || "Not listed"}</p>
                      </div>
                      <div className={`search-result-row__market search-result-row__market--${marketSignal.accent}`}>
                        <p className="search-result-row__market-headline">{marketSignal.headline}</p>
                        <p className="search-result-row__market-timer">{marketSignal.timer}</p>
                        {marketSignal.meta ? <p className="search-result-row__market-meta">{marketSignal.meta}</p> : null}
                      </div>
                      <button
                        type="button"
                        className={`search-result-row__cta${isTracked ? " search-result-row__cta--done" : ""}`}
                        onClick={() => void onAddFromSearch(result)}
                        disabled={isAdding || isTracked}
                        aria-busy={isAdding}
                        aria-label={
                          isAdding
                            ? `Adding ${result.title} to tracked lots`
                            : isTracked
                              ? `Already in tracked lots: ${result.title}`
                              : `Add to tracked lots: ${result.title}`
                        }
                        title={
                          isAdding
                            ? "Adding to tracked lots"
                            : isTracked
                              ? "This lot is already in your tracked lots"
                              : "Add to tracked lots"
                        }
                      >
                        {isAdding ? "..." : isTracked ? "✓" : "+"}
                      </button>
                    </article>
                  );
                })}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );

  return typeof document !== "undefined" ? createPortal(modal, document.body) : modal;
}
