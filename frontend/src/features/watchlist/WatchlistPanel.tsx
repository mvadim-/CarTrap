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
                <p className="muted">Lot {item.lot_number}</p>
                <div className="watchlist-card__meta muted">
                  <span>Bid {item.current_bid ?? 0} {item.currency}</span>
                  {item.sale_date ? <span>Sale {new Date(item.sale_date).toLocaleDateString()}</span> : null}
                </div>
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
