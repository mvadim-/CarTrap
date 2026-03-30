import { createPortal } from "react-dom";

import type { WatchlistHistoryEntry } from "../../types";
import { AsyncStatus } from "../shared/AsyncStatus";
import { shouldUseMobileFullscreen } from "../shared/mobileFullscreen";
import { useBodyScrollLock } from "../shared/useBodyScrollLock";

type Props = {
  title: string;
  isOpen: boolean;
  isLoading: boolean;
  error: string | null;
  entries: WatchlistHistoryEntry[];
  onClose: () => void;
};

function formatMoney(value: number | null, currency: string): string {
  if (value === null) {
    return "none";
  }
  const digits = Number.isInteger(value) ? 0 : 2;
  return `${new Intl.NumberFormat("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value)} ${currency}`;
}

function formatLocalTimestamp(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatLocalAuctionStart(value: string | null): string {
  if (!value) {
    return "none";
  }
  return formatLocalTimestamp(value);
}

function formatChangeValue(entry: WatchlistHistoryEntry, field: string, value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "none";
  }
  if ((field === "current_bid" || field === "buy_now_price") && typeof value === "number") {
    return formatMoney(value, entry.snapshot.currency);
  }
  if (field === "sale_date" && typeof value === "string") {
    return formatLocalAuctionStart(value);
  }
  return String(value);
}

function formatEntryChanges(entry: WatchlistHistoryEntry): string[] {
  const changes = entry.changes;
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
    summaries.push(`${label}: ${formatChangeValue(entry, field, change.before)} -> ${formatChangeValue(entry, field, change.after)}`);
  }

  return summaries;
}

export function LotChangeHistoryModal({ title, isOpen, isLoading, error, entries, onClose }: Props) {
  const isMobileFullscreen = shouldUseMobileFullscreen();

  useBodyScrollLock(isOpen);

  if (!isOpen) {
    return null;
  }

  const modal = (
    <div className={`modal-backdrop${isMobileFullscreen ? " modal-backdrop--mobile-screen" : ""}`} onClick={onClose}>
      <div
        aria-modal="true"
        aria-label={`${title} change history`}
        className={`modal-card history-modal${isMobileFullscreen ? " modal-card--mobile-screen" : ""}`}
        role="dialog"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <p className="eyebrow">Change history</p>
            <h3>{title}</h3>
          </div>
          <button type="button" className="ghost-button" onClick={onClose}>
            Close
          </button>
        </div>
        <div className="modal-body history-modal__body">
          {isLoading ? (
            <AsyncStatus progress="spinner" title="Loading history" message="Collecting recorded lot changes." />
          ) : error ? (
            <AsyncStatus tone="error" title="Couldn't load change history" message={error} />
          ) : entries.length === 0 ? (
            <AsyncStatus
              compact
              title="No changes recorded yet"
              message="We'll show timeline entries here after the first live update is captured for this lot."
            />
          ) : (
            <div className="history-modal__list">
              {entries.map((entry) => (
                <article key={entry.snapshot.id} className="history-entry">
                  <div className="history-entry__header">
                    <p className="history-entry__time">{formatLocalTimestamp(entry.snapshot.detected_at)}</p>
                    <span className="status-pill">{entry.snapshot.raw_status || entry.snapshot.status}</span>
                  </div>
                  <ul className="history-entry__changes">
                    {formatEntryChanges(entry).map((change) => (
                      <li key={change}>{change}</li>
                    ))}
                  </ul>
                </article>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );

  return typeof document !== "undefined" ? createPortal(modal, document.body) : modal;
}
