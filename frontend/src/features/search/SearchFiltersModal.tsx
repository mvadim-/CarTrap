import { useEffect, useState } from "react";

import {
  DRIVE_TYPE_OPTIONS,
  FUEL_TYPE_OPTIONS,
  LOT_CONDITION_OPTIONS,
  ODOMETER_RANGE_OPTIONS,
  PRIMARY_DAMAGE_OPTIONS,
  SearchFilterValues,
  TITLE_TYPE_OPTIONS,
} from "./searchFilters";

type Props = {
  isOpen: boolean;
  filters: SearchFilterValues;
  onApply: (filters: SearchFilterValues) => void;
  onClose: () => void;
};

export function SearchFiltersModal({ isOpen, filters, onApply, onClose }: Props) {
  const [draftDriveType, setDraftDriveType] = useState(filters.driveType ?? "");
  const [draftPrimaryDamage, setDraftPrimaryDamage] = useState(filters.primaryDamage ?? "");
  const [draftTitleType, setDraftTitleType] = useState(filters.titleType ?? "");
  const [draftFuelType, setDraftFuelType] = useState(filters.fuelType ?? "");
  const [draftLotCondition, setDraftLotCondition] = useState(filters.lotCondition ?? "");
  const [draftOdometerRange, setDraftOdometerRange] = useState(filters.odometerRange ?? "");

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    setDraftDriveType(filters.driveType ?? "");
    setDraftPrimaryDamage(filters.primaryDamage ?? "");
    setDraftTitleType(filters.titleType ?? "");
    setDraftFuelType(filters.fuelType ?? "");
    setDraftLotCondition(filters.lotCondition ?? "");
    setDraftOdometerRange(filters.odometerRange ?? "");
  }, [
    filters.driveType,
    filters.primaryDamage,
    filters.titleType,
    filters.fuelType,
    filters.lotCondition,
    filters.odometerRange,
    isOpen,
  ]);

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
          <label>
            Title type
            <select value={draftTitleType} onChange={(event) => setDraftTitleType(event.target.value)}>
              <option value="">Any title type</option>
              {TITLE_TYPE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Fuel type
            <select value={draftFuelType} onChange={(event) => setDraftFuelType(event.target.value)}>
              <option value="">Any fuel type</option>
              {FUEL_TYPE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Sale highlight
            <select value={draftLotCondition} onChange={(event) => setDraftLotCondition(event.target.value)}>
              <option value="">Any highlight</option>
              {LOT_CONDITION_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Odometer
            <select value={draftOdometerRange} onChange={(event) => setDraftOdometerRange(event.target.value)}>
              <option value="">Any odometer</option>
              {ODOMETER_RANGE_OPTIONS.map((option) => (
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
              setDraftTitleType("");
              setDraftFuelType("");
              setDraftLotCondition("");
              setDraftOdometerRange("");
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
                titleType: draftTitleType || undefined,
                fuelType: draftFuelType || undefined,
                lotCondition: draftLotCondition || undefined,
                odometerRange: draftOdometerRange || undefined,
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
