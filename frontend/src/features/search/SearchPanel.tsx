import { FormEvent, useState } from "react";

import type { SearchResult } from "../../types";

type Props = {
  results: SearchResult[];
  onSearch: (make: string, model: string, yearFrom: string, yearTo: string) => Promise<void>;
  onAddFromSearch: (lotUrl: string) => Promise<void>;
};

export function SearchPanel({ results, onSearch, onAddFromSearch }: Props) {
  const [make, setMake] = useState("ford");
  const [model, setModel] = useState("mustang mach-e");
  const [yearFrom, setYearFrom] = useState("2025");
  const [yearTo, setYearTo] = useState("2027");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onSearch(make, model, yearFrom, yearTo);
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
          Make
          <input value={make} onChange={(event) => setMake(event.target.value)} placeholder="Ford" />
        </label>
        <label>
          Model
          <input value={model} onChange={(event) => setModel(event.target.value)} placeholder="Mustang Mach-E" />
        </label>
        <label>
          Year From
          <input value={yearFrom} onChange={(event) => setYearFrom(event.target.value)} placeholder="2025" />
        </label>
        <label>
          Year To
          <input value={yearTo} onChange={(event) => setYearTo(event.target.value)} placeholder="2027" />
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
