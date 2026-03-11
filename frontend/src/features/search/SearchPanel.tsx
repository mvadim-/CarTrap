import { FormEvent, useState } from "react";

import type { SearchResult } from "../../types";

type Props = {
  results: SearchResult[];
  onSearch: (query: string, location: string) => Promise<void>;
  onAddFromSearch: (lotUrl: string) => Promise<void>;
};

export function SearchPanel({ results, onSearch, onAddFromSearch }: Props) {
  const [query, setQuery] = useState("toyota camry");
  const [location, setLocation] = useState("CA");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onSearch(query, location);
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Search</p>
          <h2>Manual Copart Search</h2>
        </div>
      </div>
      <form className="search-grid" onSubmit={handleSubmit}>
        <label>
          Query
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="make or model" />
        </label>
        <label>
          Location
          <input value={location} onChange={(event) => setLocation(event.target.value)} placeholder="CA - SACRAMENTO" />
        </label>
        <button type="submit">Search Lots</button>
      </form>
      <div className="result-list">
        {results.length === 0 ? (
          <p className="muted">No results loaded yet.</p>
        ) : (
          results.map((result) => (
            <article key={result.lot_number} className="result-card">
              <div>
                <strong>{result.title}</strong>
                <p className="muted">
                  Lot {result.lot_number} · {result.location ?? "Unknown location"}
                </p>
              </div>
              <div className="result-actions">
                <span className="status-pill">{result.status}</span>
                <button type="button" onClick={() => onAddFromSearch(result.url)}>
                  Add to Watchlist
                </button>
              </div>
            </article>
          ))
        )}
      </div>
    </section>
  );
}
