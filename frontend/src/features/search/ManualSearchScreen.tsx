import { FormEvent, useEffect, useState } from "react";
import { createPortal } from "react-dom";

import type { AuctionProvider } from "../../types";
import { AsyncStatus } from "../shared/AsyncStatus";
import { useBodyScrollLock } from "../shared/useBodyScrollLock";

export type SearchableOption = {
  slug: string;
  name: string;
};

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
          autoCapitalize="off"
          autoCorrect="off"
          disabled={disabled}
          placeholder={placeholder}
          spellCheck={false}
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

type Props = {
  isOpen: boolean;
  isLoadingCatalog: boolean;
  catalogReady: boolean;
  catalogError: string | null;
  onRetryCatalog: () => Promise<void>;
  manualSearchError: string | null;
  isSearching: boolean;
  makeQuery: string;
  selectedMakeLabel?: string;
  makeOptions: SearchableOption[];
  onMakeQueryChange: (value: string) => void;
  onMakeSelect: (option: SearchableOption) => void;
  modelQuery: string;
  selectedModelLabel?: string;
  modelOptions: SearchableOption[];
  onModelQueryChange: (value: string) => void;
  onModelSelect: (option: SearchableOption) => void;
  isModelDisabled: boolean;
  yearFrom: string;
  yearTo: string;
  onYearFromChange: (value: string) => void;
  onYearToChange: (value: string) => void;
  selectedProviders: AuctionProvider[];
  onToggleProvider: (provider: AuctionProvider) => void;
  activeFilterLabels: string[];
  summaryLabel: string;
  isSearchingDisabled?: boolean;
  disabledReason?: string | null;
  onOpenFilters: () => void;
  onClose: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
};

export function ManualSearchScreen({
  isOpen,
  isLoadingCatalog,
  catalogReady,
  catalogError,
  onRetryCatalog,
  manualSearchError,
  isSearching,
  makeQuery,
  selectedMakeLabel,
  makeOptions,
  onMakeQueryChange,
  onMakeSelect,
  modelQuery,
  selectedModelLabel,
  modelOptions,
  onModelQueryChange,
  onModelSelect,
  isModelDisabled,
  yearFrom,
  yearTo,
  onYearFromChange,
  onYearToChange,
  selectedProviders,
  onToggleProvider,
  activeFilterLabels,
  summaryLabel,
  isSearchingDisabled = false,
  disabledReason = null,
  onOpenFilters,
  onClose,
  onSubmit,
}: Props) {
  useBodyScrollLock(isOpen);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) {
    return null;
  }

  const screen = (
    <div className="manual-search-screen" role="dialog" aria-modal="true" aria-label="New Search">
      <header className="manual-search-screen__header">
        <div>
          <p className="eyebrow">New Search</p>
          <h3>Find Vehicles</h3>
          <p className="muted manual-search-screen__lede">
            Search across the auction sites you choose, then save the searches you want to revisit later.
          </p>
        </div>
        <button type="button" className="ghost-button" onClick={onClose}>
          Back to Inbox
        </button>
      </header>

      <div className="manual-search-screen__body">
        {isLoadingCatalog && !catalogReady ? (
          <AsyncStatus
            progress="bar"
            title="Loading vehicle list"
            message="Makes and models are loading for this device."
            className="panel-status"
          />
        ) : null}
        {catalogError ? (
          <AsyncStatus
            tone="error"
            title="Couldn't load vehicle list"
            message={catalogError}
            action={
              <button type="button" className="ghost-button" onClick={() => void onRetryCatalog()}>
                Try again
              </button>
            }
            className="panel-status"
          />
        ) : null}
        {manualSearchError ? (
          <AsyncStatus tone="error" title="Couldn't run search" message={manualSearchError} className="panel-status" />
        ) : null}
        {isSearchingDisabled && disabledReason ? (
          <AsyncStatus tone="neutral" compact message={disabledReason} className="panel-status" />
        ) : null}

        <div className="search-summary-bar search-summary-bar--screen" aria-live="polite">
          <p className="search-summary-bar__headline">{summaryLabel}</p>
          <p className="search-summary-bar__meta">
            Sites: {selectedProviders.map((provider) => provider.toUpperCase()).join(" + ")}.{" "}
            Extra filters: {activeFilterLabels.length > 0 ? activeFilterLabels.join(" · ") : "None"}
          </p>
        </div>

        {!catalogReady && !isLoadingCatalog && !catalogError ? (
          <p className="muted">The vehicle list is unavailable right now.</p>
        ) : null}

        <form className="manual-search-screen__form" onSubmit={onSubmit} aria-busy={isSearching}>
          <fieldset className="search-grid__provider-group">
            <legend>Auctions</legend>
            <div className="saved-search-inbox-toolbar" aria-label="Auction providers">
              {(["copart", "iaai"] as AuctionProvider[]).map((provider) => {
                const isSelected = selectedProviders.includes(provider);
                const label = provider === "copart" ? "Copart" : "IAAI";
                return (
                  <button
                    key={provider}
                    type="button"
                    className={`saved-search-filter-chip${isSelected ? " is-active" : ""}`}
                    aria-pressed={isSelected}
                    onClick={() => onToggleProvider(provider)}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          </fieldset>
          <SearchableSelector
            label="Make"
            ariaLabel="Make"
            query={makeQuery}
            selectedLabel={selectedMakeLabel}
            placeholder="Start typing a make"
            options={makeOptions}
            emptyMessage={catalogReady ? "No makes found." : "Loading vehicle list..."}
            disabled={isSearchingDisabled || isLoadingCatalog || !catalogReady}
            onQueryChange={onMakeQueryChange}
            onSelect={onMakeSelect}
          />
          <SearchableSelector
            label="Model"
            ariaLabel="Model"
            query={modelQuery}
            selectedLabel={selectedModelLabel}
            placeholder="Start typing a model"
            options={modelOptions}
            emptyMessage={selectedMakeLabel ? "No models found." : "Choose a make first."}
            disabled={isSearchingDisabled || isModelDisabled}
            onQueryChange={onModelQueryChange}
            onSelect={onModelSelect}
          />
          <div className="search-grid__year-group">
            <label className="search-grid__year-field">
              From year
              <input
                inputMode="numeric"
                maxLength={4}
                pattern="[0-9]*"
                value={yearFrom}
                disabled={isSearchingDisabled}
                onChange={(event) => onYearFromChange(event.target.value)}
                placeholder="2025"
              />
            </label>
            <label className="search-grid__year-field">
              To year
              <input
                inputMode="numeric"
                maxLength={4}
                pattern="[0-9]*"
                value={yearTo}
                disabled={isSearchingDisabled}
                onChange={(event) => onYearToChange(event.target.value)}
                placeholder="2027"
              />
            </label>
          </div>

          <div className="manual-search-screen__actions">
            <button
              type="button"
              className="ghost-button search-grid__filters-button"
              aria-label={activeFilterLabels.length > 0 ? `Filters (${activeFilterLabels.length} active)` : "Filters"}
              onClick={onOpenFilters}
              disabled={isSearchingDisabled}
            >
              <span>Filters</span>
              {activeFilterLabels.length > 0 ? (
                <span className="search-grid__filters-count" aria-hidden="true">
                  {activeFilterLabels.length}
                </span>
              ) : null}
            </button>
            <button type="submit" disabled={!selectedMakeLabel || isSearching || isSearchingDisabled} aria-busy={isSearching}>
              {isSearching ? "Searching..." : isSearchingDisabled ? "Reconnect account" : "Search Lots"}
            </button>
          </div>
        </form>

        {isSearching ? (
          <AsyncStatus
            compact
            progress="bar"
            title="Searching auctions"
            message="Looking for matching vehicles. This may take a moment."
            className="panel-status"
          />
        ) : null}
      </div>
    </div>
  );

  return typeof document !== "undefined" ? createPortal(screen, document.body) : screen;
}
