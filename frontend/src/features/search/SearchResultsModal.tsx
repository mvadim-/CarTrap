import { useEffect, useRef, type UIEvent } from "react";
import { createPortal } from "react-dom";

import type { SearchResult } from "../../types";
import { AsyncStatus } from "../shared/AsyncStatus";
import { LotThumbnail } from "../shared/LotThumbnail";
import { shouldUseMobileFullscreen } from "../shared/mobileFullscreen";
import { useBodyScrollLock } from "../shared/useBodyScrollLock";

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
    return "Status unavailable";
  }

  return status
    .replace(/_/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
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
  canRefreshLive = false,
  onRefreshLive,
  isRefreshingLive = false,
  lastSyncedAt = null,
  refreshError = null,
  statusMessage = null,
  mobileFullscreen = false,
}: Props) {
  const isMobileFullscreen = shouldUseMobileFullscreen(mobileFullscreen);
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
  const vehicleCountLabel = `${totalResults} ${totalResults === 1 ? "Vehicle" : "Vehicles"}`;

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
              <div ref={collapsibleRef} className="search-results-modal__collapsible">
                <div className="search-results-modal__collapsible-inner">
                  <div className="search-results-modal__heading search-results-modal__heading--mobile">
                    <h3>{title}</h3>
                  </div>
                  <div className="modal-filter-bar search-results-modal__meta">
                    <span className="muted">
                      {totalResults} {totalResults === 1 ? "lot" : "lots"} found. Current result set stays reopenable until you close it.
                    </span>
                    {lastSyncedAt ? <span className="muted">Last synced {new Date(lastSyncedAt).toLocaleString()}</span> : null}
                  </div>
                  {hasStatusPanels ? (
                    <div className="search-results-modal__status-stack">
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
              <div className="modal-filter-bar search-results-modal__meta">
                <span className="muted">
                  {totalResults} {totalResults === 1 ? "lot" : "lots"} found. Current result set stays reopenable until you close it.
                </span>
                {lastSyncedAt ? <span className="muted">Last synced {new Date(lastSyncedAt).toLocaleString()}</span> : null}
              </div>
              {hasStatusPanels ? (
                <div className="search-results-modal__status-stack">
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
                </div>
              ) : null}
            </>
          )}
        </div>
        <div ref={modalBodyRef} className="modal-body result-list search-results-modal__body" onScroll={handleBodyScroll}>
          {results.length === 0 ? (
            <p className="muted search-results-modal__empty">No lots matched this search.</p>
          ) : (
            <>
              <div className="search-results-modal__count" aria-live="polite">
                <strong>{vehicleCountLabel}</strong>
              </div>
              <div className="search-results-modal__list">
                {results.map((result) => {
                  const marketSignal = getMarketSignal(result);
                  const isAdding = addingFromSearchLotUrl === result.url;

                  return (
                    <article key={result.lot_number} className="search-result-row">
                      <LotThumbnail title={result.title} thumbnailUrl={result.thumbnail_url} />
                      <div className="search-result-row__body">
                        <div className="search-result-row__title-line">
                          <strong className="search-result-row__title">{result.title}</strong>
                          {result.is_new ? <span className="new-badge">NEW</span> : null}
                        </div>
                        <p className="search-result-row__meta">Lot#: {result.lot_number}</p>
                        <p className="search-result-row__location">{result.location ?? "Unknown location"}</p>
                        <p className="search-result-row__odometer">Odo: {result.odometer?.trim() || "N/A"}</p>
                      </div>
                      <div className={`search-result-row__market search-result-row__market--${marketSignal.accent}`}>
                        <p className="search-result-row__market-headline">{marketSignal.headline}</p>
                        <p className="search-result-row__market-timer">{marketSignal.timer}</p>
                        {marketSignal.meta ? <p className="search-result-row__market-meta">{marketSignal.meta}</p> : null}
                      </div>
                      <button
                        type="button"
                        className="search-result-row__cta"
                        onClick={() => void onAddFromSearch(result.url)}
                        disabled={isAdding}
                        aria-busy={isAdding}
                        aria-label={isAdding ? `Adding ${result.title} to watchlist` : `Add to watchlist: ${result.title}`}
                        title={isAdding ? "Adding to watchlist" : "Add to watchlist"}
                      >
                        {isAdding ? "..." : ">"}
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
