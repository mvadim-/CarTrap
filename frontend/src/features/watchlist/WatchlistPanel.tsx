import type { WatchlistItem } from "../../types";

type Props = {
  items: WatchlistItem[];
  onRemove: (id: string) => Promise<void>;
};

export function WatchlistPanel({ items, onRemove }: Props) {
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Watchlist</p>
          <h2>Tracked Lots</h2>
        </div>
      </div>
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
