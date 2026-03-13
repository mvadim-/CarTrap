import { FormEvent, useState } from "react";

import type { WatchlistItem } from "../../types";
import { LotThumbnail } from "../shared/LotThumbnail";
import { LotGalleryModal } from "./LotGalleryModal";

type Props = {
  items: WatchlistItem[];
  onAddByLotNumber: (lotNumber: string) => Promise<void>;
  onRemove: (id: string) => Promise<void>;
};

export function WatchlistPanel({ items, onAddByLotNumber, onRemove }: Props) {
  const [lotNumber, setLotNumber] = useState("");
  const [selectedLot, setSelectedLot] = useState<WatchlistItem | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!lotNumber.trim()) {
      return;
    }
    await onAddByLotNumber(lotNumber.trim());
    setLotNumber("");
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

  function getTrackedLotDetails(item: WatchlistItem) {
    return [
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
        value: item.sale_date ? new Date(item.sale_date).toLocaleDateString() : "—",
      },
    ];
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Watchlist</p>
          <h2>Tracked Lots</h2>
        </div>
      </div>
      <form className="search-grid watchlist-form" onSubmit={handleSubmit}>
        <label>
          Add by Lot Number
          <input
            value={lotNumber}
            onChange={(event) => setLotNumber(event.target.value)}
            placeholder="99251295"
          />
        </label>
        <button type="submit">Add Lot</button>
      </form>
      {items.length === 0 ? (
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
                      <dd className="watchlist-card__detail-value detail-value">{detail.value}</dd>
                    </div>
                  ))}
                </dl>
              </div>
              <div className="watchlist-card__actions">
                <button type="button" className="ghost-button" onClick={() => onRemove(item.id)}>
                  Remove
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
