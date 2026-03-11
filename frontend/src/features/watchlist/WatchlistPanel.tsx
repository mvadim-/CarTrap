import { FormEvent, useState } from "react";

import type { WatchlistItem } from "../../types";

type Props = {
  items: WatchlistItem[];
  onAddByLotNumber: (lotNumber: string) => Promise<void>;
  onRemove: (id: string) => Promise<void>;
};

export function WatchlistPanel({ items, onAddByLotNumber, onRemove }: Props) {
  const [lotNumber, setLotNumber] = useState("");

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
      <form className="search-grid" onSubmit={handleSubmit}>
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
        <div className="result-list">
          {items.map((item) => (
            <article key={item.id} className="result-card">
              <div>
                <strong>{item.title}</strong>
                <p className="muted">
                  Lot {item.lot_number} · {item.status} · {item.current_bid ?? 0} {item.currency}
                </p>
              </div>
              <button type="button" className="ghost-button" onClick={() => onRemove(item.id)}>
                Remove
              </button>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
