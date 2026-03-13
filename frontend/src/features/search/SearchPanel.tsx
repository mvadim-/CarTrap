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
import { getSearchFilterLabels, SearchFilterValues } from "./searchFilters";

type SearchableOption = {
  slug: string;
  name: string;
};

function normalizeSearchValue(value: string): string {
  return value.trim().toUpperCase();
}

function tokenizeSearchValue(value: string): string[] {
  return normalizeSearchValue(value)
    .split(/[^A-Z0-9]+/)
    .filter(Boolean);
}

function matchesMakeQuery(name: string, query: string): boolean {
  const normalizedQuery = normalizeSearchValue(query);
  if (!normalizedQuery) {
    return true;
  }
  return normalizeSearchValue(name).startsWith(normalizedQuery);
}

function matchesModelQuery(name: string, query: string): boolean {
  const queryTokens = tokenizeSearchValue(query);
  if (queryTokens.length === 0) {
    return true;
  }
  const nameTokens = tokenizeSearchValue(name);
  return queryTokens.every((queryToken) => nameTokens.some((nameToken) => nameToken.startsWith(queryToken)));
}

type SearchableSelectorProps = {
  label: string;
  ariaLabel: string;
  placeholder: string;
  query: string;
  selectedLabel?: string;
  options: SearchableOption[];
  emptyMessage: string;
  disabled?: boolean;
  onQueryChange: (value: string) => void;
  onSelect: (option: SearchableOption) => void;
};

function SearchableSelector({
  label,
  ariaLabel,
  placeholder,
  query,
  selectedLabel,
  options,
  emptyMessage,
  disabled = false,
  onQueryChange,
  onSelect,
}: SearchableSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);

  const displayValue = isOpen ? query : query || selectedLabel || "";

  return (
    <label className="searchable-select">
      {label}
      <div className="searchable-select__field">
        <input
          aria-label={ariaLabel}
          autoComplete="off"
          disabled={disabled}
          placeholder={placeholder}
          value={displayValue}
          onChange={(event) => {
            if (!isOpen) {
              setIsOpen(true);
            }
            onQueryChange(event.target.value);
          }}
          onFocus={() => setIsOpen(true)}
          onBlur={() => window.setTimeout(() => setIsOpen(false), 120)}
        />
        {isOpen ? (
          <div className="searchable-select__menu" role="listbox" aria-label={`${label} options`}>
            {options.length === 0 ? (
              <p className="searchable-select__empty muted">{emptyMessage}</p>
            ) : (
              options.map((option) => (
                <button
                  key={option.slug}
                  type="button"
                  className="searchable-select__option"
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => {
                    onSelect(option);
                    setIsOpen(false);
                  }}
                >
                  {option.name}
                </button>
              ))
            )}
          </div>
        ) : null}
      </div>
    </label>
  );
}

type SearchPayload = {
  make?: string;
  model?: string;
  makeFilter?: string;
  modelFilter?: string;
  driveType?: string;
  primaryDamage?: string;
  titleType?: string;
  fuelType?: string;
  lotCondition?: string;
  odometerRange?: string;
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
  const [makeQuery, setMakeQuery] = useState("");
  const [modelQuery, setModelQuery] = useState("");
  const [yearFrom, setYearFrom] = useState("2025");
  const [yearTo, setYearTo] = useState("2027");
  const [isResultsOpen, setIsResultsOpen] = useState(false);
  const [isFiltersOpen, setIsFiltersOpen] = useState(false);
  const [driveType, setDriveType] = useState<string | undefined>(undefined);
  const [primaryDamage, setPrimaryDamage] = useState<string | undefined>(undefined);
  const [titleType, setTitleType] = useState<string | undefined>(undefined);
  const [fuelType, setFuelType] = useState<string | undefined>(undefined);
  const [lotCondition, setLotCondition] = useState<string | undefined>(undefined);
  const [odometerRange, setOdometerRange] = useState<string | undefined>(undefined);
  const [lastSubmittedPayload, setLastSubmittedPayload] = useState<SearchPayload | null>(null);

  const filteredMakes = catalog?.makes.filter((item) => matchesMakeQuery(item.name, makeQuery)) ?? [];
  const selectedMake: SearchCatalogMake | null = catalog?.makes.find((item) => item.slug === selectedMakeSlug) ?? null;
  const filteredModels = selectedMake?.models.filter((item) => matchesModelQuery(item.name, modelQuery)) ?? [];
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
    if (!catalog) {
      return;
    }
    if (!makeQuery.trim()) {
      return;
    }
    if (filteredMakes.length === 0) {
      setSelectedMakeSlug("");
      setSelectedModelSlug("");
      return;
    }
    if (filteredMakes.some((item) => item.slug === selectedMakeSlug)) {
      return;
    }
    setSelectedMakeSlug(filteredMakes[0].slug);
    setSelectedModelSlug("");
  }, [catalog, filteredMakes, selectedMakeSlug]);

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

  useEffect(() => {
    if (!selectedMake) {
      return;
    }
    if (!modelQuery.trim()) {
      return;
    }
    if (filteredModels.length === 0) {
      setSelectedModelSlug("");
      return;
    }
    if (filteredModels.some((item) => item.slug === selectedModelSlug)) {
      return;
    }
    setSelectedModelSlug(filteredModels[0].slug);
  }, [filteredModels, selectedMake, selectedModelSlug]);

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
      titleType,
      fuelType,
      lotCondition,
      odometerRange,
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
    setMakeQuery("");
    setModelQuery("");
    setYearFrom(savedSearch.criteria.year_from?.toString() ?? "");
    setYearTo(savedSearch.criteria.year_to?.toString() ?? "");
    setDriveType(savedSearch.criteria.drive_type);
    setPrimaryDamage(savedSearch.criteria.primary_damage);
    setTitleType(savedSearch.criteria.title_type);
    setFuelType(savedSearch.criteria.fuel_type);
    setLotCondition(savedSearch.criteria.lot_condition);
    setOdometerRange(savedSearch.criteria.odometer_range);

    try {
      await runSearch({
        make: savedSearch.criteria.make,
        model: savedSearch.criteria.model,
        makeFilter: savedSearch.criteria.make_filter,
        modelFilter: savedSearch.criteria.model_filter,
        driveType: savedSearch.criteria.drive_type,
        primaryDamage: savedSearch.criteria.primary_damage,
        titleType: savedSearch.criteria.title_type,
        fuelType: savedSearch.criteria.fuel_type,
        lotCondition: savedSearch.criteria.lot_condition,
        odometerRange: savedSearch.criteria.odometer_range,
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

  const activeFilterLabels = getSearchFilterLabels({
    driveType,
    primaryDamage,
    titleType,
    fuelType,
    lotCondition,
    odometerRange,
  });

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
        <SearchableSelector
          label="Make"
          ariaLabel="Make"
          query={makeQuery}
          selectedLabel={selectedMake?.name}
          placeholder="Type make prefix"
          options={filteredMakes}
          emptyMessage={catalog ? "No makes found." : "Loading catalog..."}
          disabled={isLoadingCatalog || !catalog}
          onQueryChange={(value) => {
            setMakeQuery(value);
            setModelQuery("");
          }}
          onSelect={(option) => {
            setSelectedMakeSlug(option.slug);
            setMakeQuery("");
            setSelectedModelSlug("");
            setModelQuery("");
          }}
        />
        <SearchableSelector
          label="Model"
          ariaLabel="Model"
          query={modelQuery}
          selectedLabel={selectedModel?.name}
          placeholder="Type model word"
          options={filteredModels}
          emptyMessage={selectedMake ? "No models found." : "Select make first."}
          disabled={!selectedMake || selectedMake.models.length === 0}
          onQueryChange={(value) => setModelQuery(value)}
          onSelect={(option) => {
            setSelectedModelSlug(option.slug);
            setModelQuery("");
          }}
        />
        <div className="search-grid__year-group">
          <label className="search-grid__year-field">
            Year From
            <input
              inputMode="numeric"
              maxLength={4}
              value={yearFrom}
              onChange={(event) => setYearFrom(event.target.value)}
              placeholder="2025"
            />
          </label>
          <label className="search-grid__year-field">
            Year To
            <input
              inputMode="numeric"
              maxLength={4}
              value={yearTo}
              onChange={(event) => setYearTo(event.target.value)}
              placeholder="2027"
            />
          </label>
        </div>
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
                  {getSearchFilterLabels({
                    driveType: item.criteria.drive_type,
                    primaryDamage: item.criteria.primary_damage,
                    titleType: item.criteria.title_type,
                    fuelType: item.criteria.fuel_type,
                    lotCondition: item.criteria.lot_condition,
                    odometerRange: item.criteria.odometer_range,
                  }).length > 0 ? (
                    <p className="muted">
                      Filters:{" "}
                      {getSearchFilterLabels({
                        driveType: item.criteria.drive_type,
                        primaryDamage: item.criteria.primary_damage,
                        titleType: item.criteria.title_type,
                        fuelType: item.criteria.fuel_type,
                        lotCondition: item.criteria.lot_condition,
                        odometerRange: item.criteria.odometer_range,
                      }).join(" · ")}
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
        filters={{ driveType, primaryDamage, titleType, fuelType, lotCondition, odometerRange }}
        onApply={({
          driveType: nextDriveType,
          primaryDamage: nextPrimaryDamage,
          titleType: nextTitleType,
          fuelType: nextFuelType,
          lotCondition: nextLotCondition,
          odometerRange: nextOdometerRange,
        }: SearchFilterValues) => {
          setDriveType(nextDriveType);
          setPrimaryDamage(nextPrimaryDamage);
          setTitleType(nextTitleType);
          setFuelType(nextFuelType);
          setLotCondition(nextLotCondition);
          setOdometerRange(nextOdometerRange);
        }}
        onClose={() => setIsFiltersOpen(false)}
      />
    </section>
  );
}
