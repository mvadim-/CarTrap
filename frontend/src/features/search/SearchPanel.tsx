import { FormEvent, useEffect, useState } from "react";

import type {
  LiveSyncStatus,
  SavedSearch,
  SavedSearchResultsResponse,
  SearchCatalog,
  SearchCatalogMake,
  SearchCatalogModel,
  SearchResult,
} from "../../types";
import { AsyncStatus } from "../shared/AsyncStatus";
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
  catalogError: string | null;
  onRetryCatalog: () => Promise<void>;
  savedSearches: SavedSearch[];
  isLoadingSavedSearches: boolean;
  savedSearchesError: string | null;
  onRetrySavedSearches: () => Promise<void>;
  isSearching: boolean;
  isSavingSearch: boolean;
  openingSavedSearchId: string | null;
  refreshingSavedSearchId: string | null;
  deletingSavedSearchId: string | null;
  addingFromSearchLotUrl: string | null;
  isBrowserOffline: boolean;
  liveSyncStatus: LiveSyncStatus | null;
  onSearch: (payload: SearchPayload) => Promise<{ results: SearchResult[]; total_results: number }>;
  onSaveSearch: (payload: SearchPayload & { seedResults?: SearchResult[]; totalResults?: number }) => Promise<SavedSearch>;
  onViewSavedSearch: (id: string) => Promise<SavedSearchResultsResponse>;
  onRefreshSavedSearch: (id: string) => Promise<SavedSearchResultsResponse>;
  onDeleteSavedSearch: (id: string) => Promise<void>;
  onAddFromSearch: (lotUrl: string) => Promise<void>;
};

type SearchModalState = {
  isOpen: boolean;
  mode: "manual" | "saved";
  title: string;
  results: SearchResult[];
  totalResults: number;
  canSave: boolean;
  savedSearchId: string | null;
  lastSyncedAt: string | null;
  refreshError: string | null;
  statusMessage: string | null;
};

function formatLotCount(count: number | null | undefined): string {
  if (count === null || count === undefined) {
    return "Lot count unavailable";
  }
  return `${count} ${count === 1 ? "lot" : "lots"} found`;
}

function formatYearRange(from?: string, to?: string): string {
  if (from && to) {
    return `${from}-${to}`;
  }
  return from || to || "—";
}

function formatFilterSummary(labels: string[]): string {
  return labels.length > 0 ? labels.join(" · ") : "No filters";
}

export function SearchPanel({
  catalog,
  isLoadingCatalog,
  catalogError,
  onRetryCatalog,
  savedSearches,
  isLoadingSavedSearches,
  savedSearchesError,
  onRetrySavedSearches,
  isSearching,
  isSavingSearch,
  openingSavedSearchId,
  refreshingSavedSearchId,
  deletingSavedSearchId,
  addingFromSearchLotUrl,
  isBrowserOffline,
  liveSyncStatus,
  onSearch,
  onSaveSearch,
  onViewSavedSearch,
  onRefreshSavedSearch,
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
  const [manualSearchError, setManualSearchError] = useState<string | null>(null);
  const [savedSearchError, setSavedSearchError] = useState<string | null>(null);
  const [savedSearchNotice, setSavedSearchNotice] = useState<string | null>(null);
  const [searchModal, setSearchModal] = useState<SearchModalState>({
    isOpen: false,
    mode: "manual",
    title: "Copart Search Results",
    results: [],
    totalResults: 0,
    canSave: false,
    savedSearchId: null,
    lastSyncedAt: null,
    refreshError: null,
    statusMessage: null,
  });

  const filteredMakes = catalog?.makes.filter((item) => matchesMakeQuery(item.name, makeQuery)) ?? [];
  const selectedMake: SearchCatalogMake | null = catalog?.makes.find((item) => item.slug === selectedMakeSlug) ?? null;
  const filteredModels = selectedMake?.models.filter((item) => matchesModelQuery(item.name, modelQuery)) ?? [];
  const selectedModel: SearchCatalogModel | null = selectedMake?.models.find((item) => item.slug === selectedModelSlug) ?? null;
  const isLiveSyncUnavailable = liveSyncStatus?.status === "degraded";

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
    if (!catalog || !makeQuery.trim()) {
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
  }, [catalog, filteredMakes, makeQuery, selectedMakeSlug]);

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
    if (!selectedMake || !modelQuery.trim()) {
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
  }, [filteredModels, modelQuery, selectedMake, selectedModelSlug]);

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
    const response = await onSearch(payload);
    setLastSubmittedPayload(payload);
    setSearchModal({
      isOpen: true,
      mode: "manual",
      title: "Copart Search Results",
      results: response.results,
      totalResults: response.total_results,
      canSave: true,
      savedSearchId: null,
      lastSyncedAt: null,
      refreshError: null,
      statusMessage: null,
    });
    setIsResultsOpen(true);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedMake || isSearching) {
      return;
    }
    setManualSearchError(null);
    setSavedSearchNotice(null);
    try {
      await runSearch(buildPayload());
    } catch (error) {
      setSearchModal((current) => ({ ...current, isOpen: false }));
      setIsResultsOpen(false);
      setManualSearchError(error instanceof Error ? error.message : "Search failed.");
    }
  }

  async function handleRunSavedSearch(savedSearch: SavedSearch) {
    const matchedMake = catalog?.makes.find((item) => item.name === savedSearch.criteria.make) ?? null;
    const matchedModel = matchedMake?.models.find((item) => item.name === savedSearch.criteria.model) ?? null;

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
    setSavedSearchError(null);
    setSavedSearchNotice(null);

    try {
      const response = await onViewSavedSearch(savedSearch.id);
      setSearchModal({
        isOpen: true,
        mode: "saved",
        title: response.saved_search.label,
        results: response.results,
        totalResults: response.cached_result_count,
        canSave: false,
        savedSearchId: savedSearch.id,
        lastSyncedAt: response.last_synced_at,
        refreshError: null,
        statusMessage: "Opened cached results. Live refresh stays available from this modal.",
      });
      setIsResultsOpen(true);
    } catch (error) {
      setSearchModal((current) => ({ ...current, isOpen: false }));
      setIsResultsOpen(false);
      setSavedSearchError(error instanceof Error ? error.message : "Could not open saved search.");
    }
  }

  async function handleSaveCurrentSearch() {
    if (!lastSubmittedPayload || isSavingSearch) {
      return;
    }
    setManualSearchError(null);
    setSavedSearchError(null);
    try {
      await onSaveSearch({
        ...lastSubmittedPayload,
        seedResults: searchModal.results,
        totalResults: searchModal.totalResults,
      });
      setSavedSearchNotice("Saved search ready.");
      setSearchModal((current) => ({
        ...current,
        statusMessage: "Saved search ready. Cached results can be reopened from the saved list.",
      }));
    } catch (error) {
      setManualSearchError(error instanceof Error ? error.message : "Could not save search.");
    }
  }

  async function handleRefreshCurrentSavedSearch() {
    if (!searchModal.savedSearchId || refreshingSavedSearchId === searchModal.savedSearchId) {
      return;
    }
    setSavedSearchError(null);
    try {
      const response = await onRefreshSavedSearch(searchModal.savedSearchId);
      setSearchModal({
        isOpen: true,
        mode: "saved",
        title: response.saved_search.label,
        results: response.results,
        totalResults: response.cached_result_count,
        canSave: false,
        savedSearchId: response.saved_search.id,
        lastSyncedAt: response.last_synced_at,
        refreshError: null,
        statusMessage: "Live refresh completed. Cached results are now up to date.",
      });
      setSavedSearchNotice(`Live refresh completed for ${response.saved_search.label}.`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Could not refresh saved search.";
      setSearchModal((current) => ({
        ...current,
        refreshError: message,
        statusMessage: null,
      }));
      setSavedSearchError(message);
    }
  }

  async function handleDeleteSavedSearch(id: string) {
    setSavedSearchError(null);
    setSavedSearchNotice(null);
    try {
      await onDeleteSavedSearch(id);
      setSavedSearchNotice("Saved search removed.");
    } catch (error) {
      setSavedSearchError(error instanceof Error ? error.message : "Could not delete saved search.");
    }
  }

  function formatSavedSearchYears(item: SavedSearch): string {
    return formatYearRange(item.criteria.year_from?.toString(), item.criteria.year_to?.toString());
  }

  function formatSavedSearchCriteriaSummary(item: SavedSearch): string {
    return [item.criteria.make ?? "Any make", item.criteria.model ?? "Any model", formatSavedSearchYears(item)].join(
      " / ",
    );
  }

  function formatSavedSearchFilterSummary(item: SavedSearch): string {
    return formatFilterSummary(
      getSearchFilterLabels({
        driveType: item.criteria.drive_type,
        primaryDamage: item.criteria.primary_damage,
        titleType: item.criteria.title_type,
        fuelType: item.criteria.fuel_type,
        lotCondition: item.criteria.lot_condition,
        odometerRange: item.criteria.odometer_range,
      }),
    );
  }

  function getSavedSearchSyncState(item: SavedSearch): string {
    if (refreshingSavedSearchId === item.id) {
      return "Refreshing live now";
    }
    if (isBrowserOffline) {
      return "Device offline";
    }
    if (isLiveSyncUnavailable) {
      return "Live sync unavailable";
    }
    if (!item.last_synced_at) {
      return "Never synced";
    }
    return "Cached results ready";
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
    <section className="panel panel--search">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Search</p>
          <h2>Manual Copart Search</h2>
        </div>
      </div>
      {isLoadingCatalog && !catalog ? (
        <AsyncStatus
          progress="bar"
          title="Loading search catalog"
          message="Make and model options are loading for this device."
          className="panel-status"
        />
      ) : null}
      {catalogError ? (
        <AsyncStatus
          tone="error"
          title="Search catalog unavailable"
          message={catalogError}
          action={
            <button type="button" className="ghost-button" onClick={() => void onRetryCatalog()}>
              Retry catalog
            </button>
          }
          className="panel-status"
        />
      ) : null}
      {manualSearchError ? (
        <AsyncStatus tone="error" title="Search request failed" message={manualSearchError} className="panel-status" />
      ) : null}
      {savedSearchNotice ? (
        <AsyncStatus tone="success" compact message={savedSearchNotice} className="panel-status" />
      ) : null}
      <form className="search-grid search-grid--panel" onSubmit={handleSubmit} aria-busy={isSearching}>
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
        <div className="search-grid__actions">
          <button type="submit" disabled={!selectedMake || isSearching} aria-busy={isSearching}>
            {isSearching ? "Searching..." : "Search Lots"}
          </button>
          <button type="button" className="ghost-button" onClick={() => setIsFiltersOpen(true)}>
            Filters{activeFilterLabels.length > 0 ? ` (${activeFilterLabels.length})` : ""}
          </button>
        </div>
      </form>
      {isSearching ? (
        <AsyncStatus
          compact
          progress="bar"
          title="Searching Copart"
          message="Current filters stay in place while live results load."
          className="panel-status"
        />
      ) : null}
      <div className="search-summary-bar" aria-live="polite">
        <p className="search-summary-bar__headline">
          {selectedMake?.name ?? "Any make"} / {selectedModel?.name ?? "Any model"} / {formatYearRange(yearFrom, yearTo)}
        </p>
        <p className="search-summary-bar__meta">Filters: {formatFilterSummary(activeFilterLabels)}</p>
      </div>
      {!catalog && !isLoadingCatalog && !catalogError ? <p className="muted">Search catalog is unavailable.</p> : null}

      <div className="saved-searches">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Saved</p>
            <h3>Saved Searches</h3>
          </div>
        </div>
        {savedSearchError ? (
          <AsyncStatus tone="error" title="Saved-search action failed" message={savedSearchError} className="panel-status" />
        ) : null}
        {isLoadingSavedSearches && savedSearches.length === 0 ? (
          <AsyncStatus
            progress="spinner"
            title="Loading saved searches"
            message="Your cached search runs and freshness metadata are loading."
            className="panel-status"
          />
        ) : null}
        {savedSearchesError ? (
          <AsyncStatus
            tone="error"
            title="Saved searches unavailable"
            message={savedSearchesError}
            action={
              <button type="button" className="ghost-button" onClick={() => void onRetrySavedSearches()}>
                Retry saved searches
              </button>
            }
            className="panel-status"
          />
        ) : null}
        <div className="result-list">
          {!isLoadingSavedSearches && savedSearches.length === 0 && !savedSearchesError ? (
            <p className="muted">No saved searches yet.</p>
          ) : (
            savedSearches.map((item) => (
              <article key={item.id} className="result-card saved-search-card">
                <div className="saved-search-card__body">
                  <div className="saved-search-card__header">
                    <div className="saved-search-card__title-block">
                      <strong>{item.label}</strong>
                      <p className="saved-search-card__criteria">{formatSavedSearchCriteriaSummary(item)}</p>
                    </div>
                    {item.new_count > 0 ? <span className="new-badge">{item.new_count} NEW</span> : null}
                  </div>
                  <p className="saved-search-card__filters">Filters: {formatSavedSearchFilterSummary(item)}</p>
                  <dl className="saved-search-card__metrics">
                    <div className="saved-search-card__metric">
                      <dt className="detail-label">Matches</dt>
                      <dd className="detail-value">{formatLotCount(item.cached_result_count ?? item.result_count)}</dd>
                    </div>
                    <div className="saved-search-card__metric">
                      <dt className="detail-label">Freshness</dt>
                      <dd className="detail-value">{getSavedSearchSyncState(item)}</dd>
                    </div>
                    <div className="saved-search-card__metric">
                      <dt className="detail-label">Last synced</dt>
                      <dd className="detail-value">
                        {item.last_synced_at ? new Date(item.last_synced_at).toLocaleString() : "Not yet"}
                      </dd>
                    </div>
                  </dl>
                </div>
                <div className="saved-search-card__actions">
                  <button
                    type="button"
                    onClick={() => void handleRunSavedSearch(item)}
                    disabled={openingSavedSearchId === item.id}
                    aria-busy={openingSavedSearchId === item.id}
                  >
                    {openingSavedSearchId === item.id ? "Opening..." : "Open Results"}
                  </button>
                  <a className="ghost-button" href={item.external_url} target="_blank" rel="noreferrer">
                    Open URL
                  </a>
                  <button
                    type="button"
                    className="ghost-button"
                    onClick={() => void handleDeleteSavedSearch(item.id)}
                    disabled={deletingSavedSearchId === item.id}
                    aria-busy={deletingSavedSearchId === item.id}
                  >
                    {deletingSavedSearchId === item.id ? "Deleting..." : "Delete"}
                  </button>
                </div>
              </article>
            ))
          )}
        </div>
      </div>

      <SearchResultsModal
        isOpen={isResultsOpen && searchModal.isOpen}
        title={searchModal.title}
        results={searchModal.results}
        totalResults={searchModal.totalResults}
        onClose={() => {
          setSearchModal((current) => ({
            ...current,
            isOpen: false,
            refreshError: null,
            statusMessage: null,
          }));
          setIsResultsOpen(false);
        }}
        onAddFromSearch={onAddFromSearch}
        onSaveSearch={handleSaveCurrentSearch}
        canSave={searchModal.canSave && lastSubmittedPayload !== null}
        isSavingSearch={isSavingSearch}
        addingFromSearchLotUrl={addingFromSearchLotUrl}
        canRefreshLive={searchModal.mode === "saved" && searchModal.savedSearchId !== null}
        onRefreshLive={handleRefreshCurrentSavedSearch}
        isRefreshingLive={searchModal.savedSearchId !== null && refreshingSavedSearchId === searchModal.savedSearchId}
        lastSyncedAt={searchModal.lastSyncedAt}
        refreshError={searchModal.refreshError}
        statusMessage={searchModal.statusMessage}
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
