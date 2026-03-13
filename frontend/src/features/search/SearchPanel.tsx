import { FormEvent, useEffect, useState } from "react";

import type {
  SavedSearch,
  SearchCatalog,
  SearchCatalogMake,
  SearchCatalogModel,
  SearchResult,
} from "../../types";
import { SearchFiltersModal } from "./SearchFiltersModal";
import { SearchResultsModal } from "./SearchResultsModal";
import { getDriveTypeLabel, getPrimaryDamageLabel } from "./searchFilters";

type SearchPayload = {
  make?: string;
  model?: string;
  makeFilter?: string;
  modelFilter?: string;
  driveType?: string;
  primaryDamage?: string;
  yearFrom?: string;
  yearTo?: string;
};

type Props = {
  catalog: SearchCatalog | null;
  isLoadingCatalog: boolean;
  results: SearchResult[];
  totalResults: number;
  savedSearches: SavedSearch[];
  onSearch: (payload: SearchPayload) => Promise<void>;
  onSaveSearch: (payload: SearchPayload) => Promise<void>;
  onDeleteSavedSearch: (id: string) => Promise<void>;
  onAddFromSearch: (lotUrl: string) => Promise<void>;
};

export function SearchPanel({
  catalog,
  isLoadingCatalog,
  results,
  totalResults,
  savedSearches,
  onSearch,
  onSaveSearch,
  onDeleteSavedSearch,
  onAddFromSearch,
}: Props) {
  const [selectedMakeSlug, setSelectedMakeSlug] = useState("");
  const [selectedModelSlug, setSelectedModelSlug] = useState("");
  const [yearFrom, setYearFrom] = useState("2025");
  const [yearTo, setYearTo] = useState("2027");
  const [isResultsOpen, setIsResultsOpen] = useState(false);
  const [isFiltersOpen, setIsFiltersOpen] = useState(false);
  const [driveType, setDriveType] = useState<string | undefined>(undefined);
  const [primaryDamage, setPrimaryDamage] = useState<string | undefined>(undefined);
  const [lastSubmittedPayload, setLastSubmittedPayload] = useState<SearchPayload | null>(null);

  const selectedMake: SearchCatalogMake | null = catalog?.makes.find((item) => item.slug === selectedMakeSlug) ?? null;
  const selectedModel: SearchCatalogModel | null = selectedMake?.models.find((item) => item.slug === selectedModelSlug) ?? null;

  useEffect(() => {
    if (!catalog || catalog.makes.length === 0) {
      return;
    }
    if (!selectedMakeSlug) {
      const fallbackMake = catalog.makes.find((item) => item.slug === "ford") ?? catalog.makes[0];
      setSelectedMakeSlug(fallbackMake.slug);
      const fallbackModel =
        fallbackMake.models.find((item) => item.slug === "mustangmache") ?? fallbackMake.models[0] ?? null;
      setSelectedModelSlug(fallbackModel?.slug ?? "");
    }
  }, [catalog, selectedMakeSlug]);

  useEffect(() => {
    if (!selectedMake) {
      setSelectedModelSlug("");
      return;
    }
    if (selectedModelSlug && selectedMake.models.some((item) => item.slug === selectedModelSlug)) {
      return;
    }
    setSelectedModelSlug(selectedMake.models[0]?.slug ?? "");
  }, [selectedMake, selectedModelSlug]);

  function buildPayload(makeOverride?: SearchCatalogMake | null, modelOverride?: SearchCatalogModel | null): SearchPayload {
    const resolvedMake = makeOverride ?? selectedMake;
    const resolvedModel = modelOverride ?? selectedModel;
    return {
      make: resolvedMake?.name,
      model: resolvedModel?.name,
      makeFilter: resolvedMake?.search_filter,
      modelFilter: resolvedModel?.search_filter,
      driveType,
      primaryDamage,
      yearFrom,
      yearTo,
    };
  }

  async function runSearch(payload: SearchPayload) {
    await onSearch(payload);
    setLastSubmittedPayload(payload);
    setIsResultsOpen(true);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedMake) {
      return;
    }
    try {
      await runSearch(buildPayload());
    } catch {
      setIsResultsOpen(false);
    }
  }

  async function handleRunSavedSearch(savedSearch: SavedSearch) {
    const matchedMake = catalog?.makes.find((item) => item.name === savedSearch.criteria.make) ?? null;
    const matchedModel =
      matchedMake?.models.find((item) => item.name === savedSearch.criteria.model) ?? null;

    if (matchedMake) {
      setSelectedMakeSlug(matchedMake.slug);
      setSelectedModelSlug(matchedModel?.slug ?? "");
    }
    setYearFrom(savedSearch.criteria.year_from?.toString() ?? "");
    setYearTo(savedSearch.criteria.year_to?.toString() ?? "");
    setDriveType(savedSearch.criteria.drive_type);
    setPrimaryDamage(savedSearch.criteria.primary_damage);

    try {
      await runSearch({
        make: savedSearch.criteria.make,
        model: savedSearch.criteria.model,
        makeFilter: savedSearch.criteria.make_filter,
        modelFilter: savedSearch.criteria.model_filter,
        driveType: savedSearch.criteria.drive_type,
        primaryDamage: savedSearch.criteria.primary_damage,
        yearFrom: savedSearch.criteria.year_from?.toString(),
        yearTo: savedSearch.criteria.year_to?.toString(),
      });
    } catch {
      setIsResultsOpen(false);
    }
  }

  async function handleSaveCurrentSearch() {
    if (!lastSubmittedPayload) {
      return;
    }
    try {
      await onSaveSearch(lastSubmittedPayload);
    } catch {
      return;
    }
  }

  function formatLotCount(count: number | null | undefined): string {
    if (count === null || count === undefined) {
      return "Lot count unavailable";
    }
    return `${count} ${count === 1 ? "lot" : "lots"} found`;
  }

  const activeFilterLabels = [getDriveTypeLabel(driveType), getPrimaryDamageLabel(primaryDamage)].filter(
    (value): value is string => Boolean(value),
  );

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Search</p>
          <h2>Manual Copart Search</h2>
        </div>
        <button type="button" className="ghost-button" onClick={() => setIsFiltersOpen(true)}>
          Filters{activeFilterLabels.length > 0 ? ` (${activeFilterLabels.length})` : ""}
        </button>
      </div>
      <form className="search-grid" onSubmit={handleSubmit}>
        <label>
          Make
          <select
            aria-label="Make"
            value={selectedMakeSlug}
            onChange={(event) => {
              setSelectedMakeSlug(event.target.value);
              setSelectedModelSlug("");
            }}
            disabled={isLoadingCatalog || !catalog}
          >
            {!catalog ? <option value="">Loading catalog...</option> : null}
            {catalog?.makes.map((make) => (
              <option key={make.slug} value={make.slug}>
                {make.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Model
          <select
            aria-label="Model"
            value={selectedModelSlug}
            onChange={(event) => setSelectedModelSlug(event.target.value)}
            disabled={!selectedMake || selectedMake.models.length === 0}
          >
            {!selectedMake ? <option value="">Select make first</option> : null}
            {selectedMake && selectedMake.models.length === 0 ? <option value="">No cataloged models</option> : null}
            {selectedMake?.models.map((model) => (
              <option key={model.slug} value={model.slug}>
                {model.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Year From
          <input value={yearFrom} onChange={(event) => setYearFrom(event.target.value)} placeholder="2025" />
        </label>
        <label>
          Year To
          <input value={yearTo} onChange={(event) => setYearTo(event.target.value)} placeholder="2027" />
        </label>
        <button type="submit" disabled={!selectedMake}>
          Search Lots
        </button>
      </form>
      {activeFilterLabels.length > 0 ? (
        <p className="muted filter-summary">Active filters: {activeFilterLabels.join(" · ")}</p>
      ) : null}
      {!catalog && !isLoadingCatalog ? <p className="muted">Search catalog is unavailable.</p> : null}

      <div className="saved-searches">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Saved</p>
            <h3>Saved Searches</h3>
          </div>
        </div>
        <div className="result-list">
          {savedSearches.length === 0 ? (
            <p className="muted">No saved searches yet.</p>
          ) : (
            savedSearches.map((item) => (
              <article key={item.id} className="result-card">
                <div className="result-copy">
                  <strong>{item.label}</strong>
                  <p className="muted">
                    {item.criteria.make ?? "Unknown make"}
                    {item.criteria.model ? ` · ${item.criteria.model}` : ""}
                    {item.criteria.year_from || item.criteria.year_to
                      ? ` · ${item.criteria.year_from ?? item.criteria.year_to}-${item.criteria.year_to ?? item.criteria.year_from}`
                      : ""}
                  </p>
                  {[getDriveTypeLabel(item.criteria.drive_type), getPrimaryDamageLabel(item.criteria.primary_damage)].some(Boolean) ? (
                    <p className="muted">
                      Filters:{" "}
                      {[getDriveTypeLabel(item.criteria.drive_type), getPrimaryDamageLabel(item.criteria.primary_damage)]
                        .filter((value): value is string => Boolean(value))
                        .join(" · ")}
                    </p>
                  ) : null}
                  <p className="muted saved-search-count">{formatLotCount(item.result_count)}</p>
                </div>
                <div className="result-actions">
                  <button type="button" className="ghost-button" onClick={() => void handleRunSavedSearch(item)}>
                    Run Search
                  </button>
                  <a className="ghost-button" href={item.external_url} target="_blank" rel="noreferrer">
                    Open URL
                  </a>
                  <button type="button" className="ghost-button" onClick={() => void onDeleteSavedSearch(item.id)}>
                    Delete
                  </button>
                </div>
              </article>
            ))
          )}
        </div>
      </div>

      <SearchResultsModal
        isOpen={isResultsOpen}
        results={results}
        totalResults={totalResults}
        onClose={() => setIsResultsOpen(false)}
        onAddFromSearch={onAddFromSearch}
        onSaveSearch={handleSaveCurrentSearch}
        canSave={lastSubmittedPayload !== null}
      />
      <SearchFiltersModal
        isOpen={isFiltersOpen}
        filters={{ driveType, primaryDamage }}
        onApply={({ driveType: nextDriveType, primaryDamage: nextPrimaryDamage }) => {
          setDriveType(nextDriveType);
          setPrimaryDamage(nextPrimaryDamage);
        }}
        onClose={() => setIsFiltersOpen(false)}
      />
    </section>
  );
}
