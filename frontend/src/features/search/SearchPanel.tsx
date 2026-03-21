import { FormEvent, useEffect, useState } from "react";

import type {
  FreshnessEnvelope,
  LiveSyncStatus,
  RefreshState,
  SavedSearch,
  SavedSearchResultsResponse,
  SearchCatalog,
  SearchCatalogMake,
  SearchCatalogModel,
  SearchResult,
} from "../../types";
import { AsyncStatus } from "../shared/AsyncStatus";
import { ManualSearchScreen, type SearchableOption } from "./ManualSearchScreen";
import { SearchFiltersModal } from "./SearchFiltersModal";
import { SearchResultsModal } from "./SearchResultsModal";
import { getSearchFilterLabels } from "./searchFilters";

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
  trackedLotUrls: string[];
  isBrowserOffline: boolean;
  liveSyncStatus: LiveSyncStatus | null;
  isManualSearchOpen: boolean;
  onOpenManualSearch: () => void;
  onCloseManualSearch: () => void;
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
  freshness: FreshnessEnvelope | null;
  refreshState: RefreshState | null;
  refreshError: string | null;
  statusMessage: string | null;
};

type SavedSearchQuickFilter = "all" | "new" | "needs-refresh";

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

function formatPriorityLabel(value: string | null): string {
  if (!value) {
    return "—";
  }
  return value.replace(/_/g, " ");
}

function formatTimestamp(value: string | null, fallback = "Not yet"): string {
  return value ? new Date(value).toLocaleString() : fallback;
}

function isSavedSearchNeedingRefresh(item: SavedSearch): boolean {
  return (
    item.refresh_state.status !== "idle" ||
    item.freshness.status === "outdated" ||
    item.freshness.status === "degraded" ||
    item.freshness.status === "unknown"
  );
}

function getSavedSearchSortTimestamp(item: SavedSearch): number {
  return new Date(item.last_synced_at ?? item.created_at).getTime() || 0;
}

function getSavedSearchPriority(item: SavedSearch): number {
  if (item.new_count > 0) {
    return 0;
  }
  if (isSavedSearchNeedingRefresh(item)) {
    return 1;
  }
  if (item.freshness.status === "cached") {
    return 2;
  }
  return 3;
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

function formatLastSyncedLabel(value: string | null): string {
  return formatTimestamp(value);
}

function filterMatchesSavedSearch(item: SavedSearch, filter: SavedSearchQuickFilter): boolean {
  switch (filter) {
    case "new":
      return item.new_count > 0;
    case "needs-refresh":
      return isSavedSearchNeedingRefresh(item);
    default:
      return true;
  }
}

function getSavedSearchReliability(
  item: SavedSearch,
  refreshingSavedSearchId: string | null,
): { label: string; tone: "live" | "cached" | "warning" | "danger" | "refreshing"; detail: string; needsAttention: boolean } {
  if (refreshingSavedSearchId === item.id) {
    return {
      label: "Refreshing",
      tone: "refreshing",
      detail: "Fetching the latest live results while cached matches stay visible.",
      needsAttention: false,
    };
  }

  if (item.refresh_state.status === "repair_pending") {
    return {
      label: "Repair pending",
      tone: "refreshing",
      detail: "Compatibility repair is queued for this saved search.",
      needsAttention: true,
    };
  }

  if (item.refresh_state.status === "retryable_failure") {
    return {
      label: "Degraded",
      tone: "warning",
      detail:
        item.refresh_state.error_message ??
        `Last live refresh failed. Retry scheduled after ${formatTimestamp(item.refresh_state.next_retry_at, "the next worker run")}.`,
      needsAttention: true,
    };
  }

  if (item.refresh_state.status === "failed") {
    return {
      label: "Outdated",
      tone: "danger",
      detail: item.refresh_state.error_message ?? "Last live refresh failed and requires manual intervention.",
      needsAttention: true,
    };
  }

  switch (item.freshness.status) {
    case "live":
      return {
        label: "Live",
        tone: "live",
        detail: `Last successful sync ${formatTimestamp(item.freshness.last_synced_at)}.`,
        needsAttention: false,
      };
    case "cached":
      return {
        label: "Cached",
        tone: "cached",
        detail: item.freshness.degraded_reason
          ? `Showing cached snapshot while live sync is degraded: ${item.freshness.degraded_reason}`
          : `Showing cached snapshot from ${formatTimestamp(item.freshness.last_synced_at)}.`,
        needsAttention: false,
      };
    case "degraded":
      return {
        label: "Degraded",
        tone: "warning",
        detail:
          item.freshness.degraded_reason ??
          "Live sync is degraded. Cached results remain available until refresh recovers.",
        needsAttention: true,
      };
    case "outdated":
      return {
        label: "Outdated",
        tone: "danger",
        detail: `Last successful sync ${formatTimestamp(item.freshness.last_synced_at)}. Run Refresh Live to retry now.`,
        needsAttention: true,
      };
    default:
      return {
        label: "Awaiting sync",
        tone: "warning",
        detail: "This saved search does not have a successful live snapshot yet.",
        needsAttention: true,
      };
  }
}

function buildSavedSearchTitleButtonLabel(item: SavedSearch): string {
  return `${item.label} ${formatSavedSearchCriteriaSummary(item)}`;
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
  trackedLotUrls,
  isBrowserOffline,
  liveSyncStatus,
  isManualSearchOpen,
  onOpenManualSearch,
  onCloseManualSearch,
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
  const [quickFilter, setQuickFilter] = useState<SavedSearchQuickFilter>("all");
  const [openSavedSearchMenuId, setOpenSavedSearchMenuId] = useState<string | null>(null);
  const [highlightedSavedSearchId, setHighlightedSavedSearchId] = useState<string | null>(null);
  const [searchModal, setSearchModal] = useState<SearchModalState>({
    isOpen: false,
    mode: "manual",
    title: "Copart Search Results",
    results: [],
    totalResults: 0,
    canSave: false,
    savedSearchId: null,
    lastSyncedAt: null,
    freshness: null,
    refreshState: null,
    refreshError: null,
    statusMessage: null,
  });

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

  useEffect(() => {
    if (!openSavedSearchMenuId) {
      return;
    }

    function handlePointerDown(event: MouseEvent) {
      const target = event.target;
      if (!(target instanceof Element)) {
        return;
      }
      if (target.closest("[data-saved-search-menu]") || target.closest("[data-saved-search-menu-trigger]")) {
        return;
      }
      setOpenSavedSearchMenuId(null);
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpenSavedSearchMenuId(null);
      }
    }

    document.addEventListener("mousedown", handlePointerDown);
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [openSavedSearchMenuId]);

  useEffect(() => {
    if (!searchModal.isOpen || searchModal.mode !== "saved" || !searchModal.savedSearchId) {
      return;
    }
    const activeSavedSearch = savedSearches.find((item) => item.id === searchModal.savedSearchId);
    if (!activeSavedSearch) {
      return;
    }
    setSearchModal((current) =>
      current.savedSearchId === activeSavedSearch.id
        ? {
            ...current,
            title: activeSavedSearch.label,
            lastSyncedAt: activeSavedSearch.last_synced_at,
            freshness: activeSavedSearch.freshness,
            refreshState: activeSavedSearch.refresh_state,
          }
        : current,
    );
  }, [savedSearches, searchModal.isOpen, searchModal.mode, searchModal.savedSearchId]);

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

  function openSavedSearchModal(response: SavedSearchResultsResponse, statusMessage: string | null) {
    setSearchModal({
      isOpen: true,
      mode: "saved",
      title: response.saved_search.label,
      results: response.results,
      totalResults: response.cached_result_count,
      canSave: false,
      savedSearchId: response.saved_search.id,
      lastSyncedAt: response.last_synced_at,
      freshness: response.saved_search.freshness,
      refreshState: response.saved_search.refresh_state,
      refreshError: null,
      statusMessage,
    });
    setIsResultsOpen(true);
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
      freshness: null,
      refreshState: null,
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
    setOpenSavedSearchMenuId(null);
    setHighlightedSavedSearchId(null);

    try {
      const response = await onViewSavedSearch(savedSearch.id);
      openSavedSearchModal(response, "Opened cached results. Live refresh stays available from this modal.");
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
      const saved = await onSaveSearch({
        ...lastSubmittedPayload,
        seedResults: searchModal.results,
        totalResults: searchModal.totalResults,
      });
      setQuickFilter("all");
      setSavedSearchNotice("Saved search ready.");
      setHighlightedSavedSearchId(saved.id);
      setSearchModal((current) => ({
        ...current,
        isOpen: false,
        refreshError: null,
        statusMessage: null,
      }));
      setIsResultsOpen(false);
      onCloseManualSearch();
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
      openSavedSearchModal(response, "Live refresh completed. Cached results are now up to date.");
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

  async function handleRefreshSavedSearchFromList(savedSearch: SavedSearch) {
    setSavedSearchError(null);
    setSavedSearchNotice(null);
    setOpenSavedSearchMenuId(null);
    try {
      const response = await onRefreshSavedSearch(savedSearch.id);
      openSavedSearchModal(response, "Live refresh completed. Cached results are now up to date.");
      setSavedSearchNotice(`Live refresh completed for ${response.saved_search.label}.`);
    } catch (error) {
      setSavedSearchError(error instanceof Error ? error.message : "Could not refresh saved search.");
    }
  }

  async function handleDeleteSavedSearch(id: string) {
    setSavedSearchError(null);
    setSavedSearchNotice(null);
    setOpenSavedSearchMenuId(null);
    try {
      await onDeleteSavedSearch(id);
      if (highlightedSavedSearchId === id) {
        setHighlightedSavedSearchId(null);
      }
      setSavedSearchNotice("Saved search removed.");
    } catch (error) {
      setSavedSearchError(error instanceof Error ? error.message : "Could not delete saved search.");
    }
  }

  const activeFilterLabels = getSearchFilterLabels({
    driveType,
    primaryDamage,
    titleType,
    fuelType,
    lotCondition,
    odometerRange,
  });

  const summaryLabel = `${selectedMake?.name ?? "Any make"} / ${selectedModel?.name ?? "Any model"} / ${formatYearRange(
    yearFrom,
    yearTo,
  )}`;
  const quickFilterCounts = {
    all: savedSearches.length,
    new: savedSearches.filter((item) => item.new_count > 0).length,
    "needs-refresh": savedSearches.filter((item) => isSavedSearchNeedingRefresh(item)).length,
  };
  const visibleSavedSearches = [...savedSearches]
    .sort((left, right) => {
      const priorityDelta = getSavedSearchPriority(left) - getSavedSearchPriority(right);
      if (priorityDelta !== 0) {
        return priorityDelta;
      }
      const timestampDelta = getSavedSearchSortTimestamp(right) - getSavedSearchSortTimestamp(left);
      if (timestampDelta !== 0) {
        return timestampDelta;
      }
      return left.label.localeCompare(right.label);
    })
    .filter((item) => filterMatchesSavedSearch(item, quickFilter));
  const hasVisibleSavedSearches = visibleSavedSearches.length > 0;

  const makeOptions: SearchableOption[] = filteredMakes.map((item) => ({ slug: item.slug, name: item.name }));
  const modelOptions: SearchableOption[] = filteredModels.map((item) => ({ slug: item.slug, name: item.name }));

  async function handleAddCurrentResultToWatchlist(lotUrl: string) {
    await onAddFromSearch(lotUrl);
    const addedResult = searchModal.results.find((item) => item.url === lotUrl);
    setSearchModal((current) => ({
      ...current,
      statusMessage: addedResult ? `Added ${addedResult.title} to watchlist.` : "Lot added to watchlist.",
      refreshError: null,
    }));
  }

  return (
    <>
      <section className="panel panel--search panel--operational search-panel">
        <div className="panel-header search-panel__header">
          <div>
            <p className="eyebrow">Inbox</p>
            <h2>Saved Searches</h2>
            <p className="muted search-panel__lede">
              Open cached results from the title block, surface new matches first, and push manual search into a
              secondary flow.
            </p>
          </div>
          <button type="button" className="ghost-button search-panel__new-search-button" onClick={onOpenManualSearch}>
            New Search
          </button>
        </div>

        {savedSearchNotice ? (
          <AsyncStatus tone="success" compact message={savedSearchNotice} className="panel-status" />
        ) : null}
        {savedSearchError ? (
          <AsyncStatus tone="error" title="Saved-search action failed" message={savedSearchError} className="panel-status" />
        ) : null}

        <div className="saved-search-inbox-toolbar" aria-label="Saved search filters">
          <button
            type="button"
            className={`saved-search-filter-chip${quickFilter === "all" ? " is-active" : ""}`}
            aria-pressed={quickFilter === "all"}
            onClick={() => setQuickFilter("all")}
          >
            All
            <span aria-hidden="true">{quickFilterCounts.all}</span>
          </button>
          <button
            type="button"
            className={`saved-search-filter-chip${quickFilter === "new" ? " is-active" : ""}`}
            aria-pressed={quickFilter === "new"}
            onClick={() => setQuickFilter("new")}
          >
            New
            <span aria-hidden="true">{quickFilterCounts.new}</span>
          </button>
          <button
            type="button"
            className={`saved-search-filter-chip${quickFilter === "needs-refresh" ? " is-active" : ""}`}
            aria-pressed={quickFilter === "needs-refresh"}
            onClick={() => setQuickFilter("needs-refresh")}
          >
            Needs refresh
            <span aria-hidden="true">{quickFilterCounts["needs-refresh"]}</span>
          </button>
        </div>

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

        <div className="result-list saved-search-inbox">
          {!isLoadingSavedSearches && savedSearches.length === 0 && !savedSearchesError ? (
            <div className="saved-search-empty-state">
              <p className="saved-search-empty-state__title">No saved searches yet.</p>
              <p className="muted">
                Start with a manual search, then save the result set you want this inbox to monitor.
              </p>
              <button type="button" onClick={onOpenManualSearch}>
                New Search
              </button>
            </div>
          ) : null}

          {!savedSearchesError && savedSearches.length > 0 && !hasVisibleSavedSearches ? (
            <div className="saved-search-empty-state saved-search-empty-state--filtered">
              <p className="saved-search-empty-state__title">No searches match this filter.</p>
              <p className="muted">Try another inbox filter or start a new saved search.</p>
              <div className="saved-search-empty-state__actions">
                <button type="button" className="ghost-button" onClick={() => setQuickFilter("all")}>
                  Show all
                </button>
                <button type="button" onClick={onOpenManualSearch}>
                  New Search
                </button>
              </div>
            </div>
          ) : null}

          {visibleSavedSearches.map((item) => {
            const isMenuOpen = openSavedSearchMenuId === item.id;
            const isHighlighted = highlightedSavedSearchId === item.id;
            const reliability = getSavedSearchReliability(item, refreshingSavedSearchId);

            return (
              <article
                key={item.id}
                className={`result-card saved-search-card${isHighlighted ? " saved-search-card--highlighted" : ""}${reliability.needsAttention ? " saved-search-card--attention" : ""}`}
              >
                <div className="saved-search-card__body">
                  <div className="saved-search-card__header">
                    <button
                      type="button"
                      className="saved-search-card__title-button"
                      onClick={() => void handleRunSavedSearch(item)}
                      disabled={openingSavedSearchId === item.id}
                      aria-busy={openingSavedSearchId === item.id}
                    >
                      <div className="saved-search-card__title-block">
                        <strong>{item.label}</strong>
                        <p className="saved-search-card__criteria">{formatSavedSearchCriteriaSummary(item)}</p>
                      </div>
                      <span className="saved-search-card__open-label">
                        {openingSavedSearchId === item.id ? "Opening..." : "Open cached results"}
                      </span>
                      <span className="sr-only">{buildSavedSearchTitleButtonLabel(item)}</span>
                    </button>
                    <div className="saved-search-card__header-badges">
                      {isHighlighted ? <span className="saved-search-card__saved-badge">Just saved</span> : null}
                      {item.new_count > 0 ? <span className="new-badge">{item.new_count} NEW</span> : null}
                    </div>
                  </div>

                  <p className="saved-search-card__filters">Filters: {formatSavedSearchFilterSummary(item)}</p>

                  <div className="saved-search-card__reliability">
                    <span className={`status-pill status-pill--${reliability.tone}`}>{reliability.label}</span>
                    <p className="saved-search-card__reliability-copy">{reliability.detail}</p>
                  </div>

                  <dl className="saved-search-card__metrics">
                    <div className="saved-search-card__metric">
                      <dt className="detail-label">Matches</dt>
                      <dd className="detail-value">{formatLotCount(item.cached_result_count ?? item.result_count)}</dd>
                    </div>
                    <div className="saved-search-card__metric">
                      <dt className="detail-label">Priority</dt>
                      <dd className="detail-value">{formatPriorityLabel(item.refresh_state.priority_class)}</dd>
                    </div>
                    <div className="saved-search-card__metric">
                      <dt className="detail-label">Last synced</dt>
                      <dd className="detail-value">{formatLastSyncedLabel(item.last_synced_at)}</dd>
                    </div>
                  </dl>
                </div>

                <div className="saved-search-card__actions">
                  <button
                    type="button"
                    className="ghost-button saved-search-card__menu-trigger"
                    data-saved-search-menu-trigger="true"
                    aria-expanded={isMenuOpen}
                    aria-haspopup="menu"
                    aria-label={`More actions for ${item.label}`}
                    onClick={() => setOpenSavedSearchMenuId((current) => (current === item.id ? null : item.id))}
                  >
                    More
                  </button>

                  {isMenuOpen ? (
                    <div className="saved-search-actions-menu" role="menu" data-saved-search-menu="true">
                      <button
                        type="button"
                        role="menuitem"
                        className="saved-search-actions-menu__item"
                        onClick={() => void handleRefreshSavedSearchFromList(item)}
                        disabled={refreshingSavedSearchId === item.id}
                      >
                        {refreshingSavedSearchId === item.id ? "Refreshing..." : "Refresh Live"}
                      </button>
                      <a
                        role="menuitem"
                        className="saved-search-actions-menu__item"
                        href={item.external_url}
                        target="_blank"
                        rel="noreferrer"
                        onClick={() => setOpenSavedSearchMenuId(null)}
                      >
                        Open URL
                      </a>
                      <button
                        type="button"
                        role="menuitem"
                        className="saved-search-actions-menu__item saved-search-actions-menu__item--danger"
                        onClick={() => void handleDeleteSavedSearch(item.id)}
                        disabled={deletingSavedSearchId === item.id}
                      >
                        {deletingSavedSearchId === item.id ? "Deleting..." : "Delete"}
                      </button>
                    </div>
                  ) : null}
                </div>
              </article>
            );
          })}
        </div>

        <div className="search-panel__sticky-cta">
          <button type="button" className="search-panel__sticky-button" onClick={onOpenManualSearch}>
            New Search
          </button>
        </div>
      </section>

      <ManualSearchScreen
        isOpen={isManualSearchOpen}
        isLoadingCatalog={isLoadingCatalog}
        catalogReady={catalog !== null}
        catalogError={catalogError}
        onRetryCatalog={onRetryCatalog}
        manualSearchError={manualSearchError}
        isSearching={isSearching}
        makeQuery={makeQuery}
        selectedMakeLabel={selectedMake?.name}
        makeOptions={makeOptions}
        onMakeQueryChange={(value) => {
          setMakeQuery(value);
          setModelQuery("");
        }}
        onMakeSelect={(option) => {
          setSelectedMakeSlug(option.slug);
          setMakeQuery("");
          setSelectedModelSlug("");
          setModelQuery("");
        }}
        modelQuery={modelQuery}
        selectedModelLabel={selectedModel?.name}
        modelOptions={modelOptions}
        onModelQueryChange={(value) => setModelQuery(value)}
        onModelSelect={(option) => {
          setSelectedModelSlug(option.slug);
          setModelQuery("");
        }}
        isModelDisabled={!selectedMake || selectedMake.models.length === 0}
        yearFrom={yearFrom}
        yearTo={yearTo}
        onYearFromChange={setYearFrom}
        onYearToChange={setYearTo}
        activeFilterLabels={activeFilterLabels}
        summaryLabel={summaryLabel}
        onOpenFilters={() => setIsFiltersOpen(true)}
        onClose={onCloseManualSearch}
        onSubmit={handleSubmit}
      />

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
        onAddFromSearch={handleAddCurrentResultToWatchlist}
        onSaveSearch={handleSaveCurrentSearch}
        canSave={searchModal.canSave && lastSubmittedPayload !== null}
        isSavingSearch={isSavingSearch}
        addingFromSearchLotUrl={addingFromSearchLotUrl}
        trackedLotUrls={trackedLotUrls}
        canRefreshLive={searchModal.mode === "saved" && searchModal.savedSearchId !== null}
        onRefreshLive={handleRefreshCurrentSavedSearch}
        isRefreshingLive={
          searchModal.savedSearchId !== null && refreshingSavedSearchId === searchModal.savedSearchId
        }
        lastSyncedAt={searchModal.lastSyncedAt}
        freshness={searchModal.freshness}
        refreshState={searchModal.refreshState}
        refreshError={searchModal.refreshError}
        statusMessage={searchModal.statusMessage}
        mobileFullscreen={searchModal.mode === "saved"}
      />

      <SearchFiltersModal
        isOpen={isFiltersOpen}
        filters={{
          driveType,
          primaryDamage,
          titleType,
          fuelType,
          lotCondition,
          odometerRange,
        }}
        onApply={(filters) => {
          setDriveType(filters.driveType);
          setPrimaryDamage(filters.primaryDamage);
          setTitleType(filters.titleType);
          setFuelType(filters.fuelType);
          setLotCondition(filters.lotCondition);
          setOdometerRange(filters.odometerRange);
        }}
        onClose={() => setIsFiltersOpen(false)}
      />
    </>
  );
}
