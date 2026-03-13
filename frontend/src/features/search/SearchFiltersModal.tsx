import { useEffect, useState } from "react";

import {
  DRIVE_TYPE_OPTIONS,
  PRIMARY_DAMAGE_OPTIONS,
} from "./searchFilters";

type SearchFilterValues = {
  driveType?: string;
  primaryDamage?: string;
};

type Props = {
  isOpen: boolean;
  filters: SearchFilterValues;
  onApply: (filters: SearchFilterValues) => void;
  onClose: () => void;
};

export function SearchFiltersModal({ isOpen, filters, onApply, onClose }: Props) {
  const [draftDriveType, setDraftDriveType] = useState(filters.driveType ?? "");
  const [draftPrimaryDamage, setDraftPrimaryDamage] = useState(filters.primaryDamage ?? "");

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    setDraftDriveType(filters.driveType ?? "");
    setDraftPrimaryDamage(filters.primaryDamage ?? "");
  }, [filters.driveType, filters.primaryDamage, isOpen]);

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

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        aria-modal="true"
        className="modal-card filter-modal"
        role="dialog"
        aria-label="Search filters"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <p className="eyebrow">Filters</p>
            <h3>Additional Search Filters</h3>
          </div>
          <button type="button" className="ghost-button" onClick={onClose}>
            Close
          </button>
        </div>
        <div className="modal-body filter-grid">
          <label>
            Drive train
            <select value={draftDriveType} onChange={(event) => setDraftDriveType(event.target.value)}>
              <option value="">Any drive train</option>
              {DRIVE_TYPE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Primary damage
            <select value={draftPrimaryDamage} onChange={(event) => setDraftPrimaryDamage(event.target.value)}>
              <option value="">Any primary damage</option>
              {PRIMARY_DAMAGE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="modal-header filter-modal__actions">
          <button
            type="button"
            className="ghost-button"
            onClick={() => {
              setDraftDriveType("");
              setDraftPrimaryDamage("");
            }}
          >
            Clear
          </button>
          <button
            type="button"
            onClick={() => {
              onApply({
                driveType: draftDriveType || undefined,
                primaryDamage: draftPrimaryDamage || undefined,
              });
              onClose();
            }}
          >
            Apply Filters
          </button>
        </div>
      </div>
    </div>
  );
}
