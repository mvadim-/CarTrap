import { FormEvent, useEffect } from "react";
import { createPortal } from "react-dom";

import type { AuctionProvider, ProviderConnectionDiagnostic } from "../../types";
import { AsyncStatus } from "../shared/AsyncStatus";
import { AUCTION_PROVIDER_OPTIONS, AuctionProviderBadge, getAuctionProviderLabel } from "../shared/AuctionProviderBadge";
import { shouldUseMobileFullscreen } from "../shared/mobileFullscreen";
import { useBodyScrollLock } from "../shared/useBodyScrollLock";

type Props = {
  isOpen: boolean;
  manualProvider: AuctionProvider;
  lotNumber: string;
  isAddingLot: boolean;
  isManualActionBlocked: boolean;
  selectedDiagnostic: ProviderConnectionDiagnostic | null;
  actionError: string | null;
  onClose: () => void;
  onManualProviderChange: (provider: AuctionProvider) => void;
  onLotNumberChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
};

export function TrackLotModal({
  isOpen,
  manualProvider,
  lotNumber,
  isAddingLot,
  isManualActionBlocked,
  selectedDiagnostic,
  actionError,
  onClose,
  onManualProviderChange,
  onLotNumberChange,
  onSubmit,
}: Props) {
  const isMobileFullscreen = shouldUseMobileFullscreen();
  const manualProviderLabel = getAuctionProviderLabel(manualProvider);
  const providerArticle = manualProvider === "iaai" ? "an" : "a";
  const identifierLabel = manualProvider === "iaai" ? "Stock or item ID" : "Lot number";
  const identifierPlaceholder = manualProvider === "copart" ? "99251295" : "STK-44 or 42153827";
  const identifierHint =
    manualProvider === "copart"
      ? "Enter the Copart lot number from the listing."
      : "Enter the IAAI stock number or item ID from the listing.";

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

  const modal = (
    <div className={`modal-backdrop${isMobileFullscreen ? " modal-backdrop--mobile-screen" : ""}`} onClick={onClose}>
      <div
        aria-modal="true"
        aria-label="Track lot"
        className={`modal-card track-lot-modal${isMobileFullscreen ? " modal-card--mobile-screen track-lot-modal--mobile" : ""}`}
        role="dialog"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <p className="eyebrow">Watchlist</p>
            <h3>Track Lot</h3>
            <p className="muted track-lot-modal__lede">
              Add {providerArticle} {manualProviderLabel} listing to this watchlist and keep the main list focused on active lots.
            </p>
          </div>
          <button type="button" className="ghost-button" onClick={onClose}>
            {isMobileFullscreen ? "Back to Watchlist" : "Close"}
          </button>
        </div>
        <div className="modal-body track-lot-modal__body">
          {isManualActionBlocked && selectedDiagnostic ? (
            <AsyncStatus tone="neutral" compact message={selectedDiagnostic.message} className="panel-status" />
          ) : null}
          {actionError ? <AsyncStatus tone="error" title="Couldn't track this lot" message={actionError} className="panel-status" /> : null}
          {isAddingLot ? (
            <AsyncStatus
              compact
              progress="bar"
              title="Tracking lot"
              message="We'll keep your current list visible while we load the details."
              className="panel-status"
            />
          ) : null}

          <form className="track-lot-modal__form" onSubmit={onSubmit} aria-busy={isAddingLot}>
            <fieldset className="track-lot-modal__field track-lot-modal__field--provider">
              <legend className="track-lot-modal__label">Auction site</legend>
              <div className="track-lot-modal__provider-group">
                {AUCTION_PROVIDER_OPTIONS.map((option) => {
                  const isSelected = manualProvider === option.value;

                  return (
                    <button
                      key={option.value}
                      type="button"
                      className={`track-lot-modal__provider-button${isSelected ? " is-active" : ""}`}
                      aria-pressed={isSelected}
                      onClick={() => onManualProviderChange(option.value)}
                    >
                      <AuctionProviderBadge provider={option.value} size="default" tone="plain" className="track-lot-modal__provider-badge" />
                    </button>
                  );
                })}
              </div>
            </fieldset>

            <label className="track-lot-modal__field">
              <span className="track-lot-modal__label">{identifierLabel}</span>
              <input
                name="lot_identifier"
                value={lotNumber}
                onChange={(event) => onLotNumberChange(event.target.value)}
                inputMode={manualProvider === "copart" ? "numeric" : "text"}
                pattern={manualProvider === "copart" ? "[0-9]*" : undefined}
                autoComplete="off"
                autoCapitalize="off"
                autoCorrect="off"
                spellCheck={false}
                placeholder={identifierPlaceholder}
                aria-describedby="track-lot-modal-hint"
                disabled={isManualActionBlocked}
              />
            </label>

            <div className="track-lot-modal__actions">
              <button
                type="button"
                className="ghost-button"
                onClick={onClose}
                disabled={isAddingLot}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="track-lot-modal__submit"
                disabled={!lotNumber.trim() || isAddingLot || isManualActionBlocked}
                aria-busy={isAddingLot}
              >
                {isAddingLot ? "Tracking…" : "Track Lot"}
              </button>
            </div>

            <p id="track-lot-modal-hint" className="track-lot-modal__hint">
              {identifierHint}
            </p>
          </form>
        </div>
      </div>
    </div>
  );

  return typeof document !== "undefined" ? createPortal(modal, document.body) : modal;
}
