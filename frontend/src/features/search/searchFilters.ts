export type SearchFilterOption = {
  label: string;
  value: string;
};

export type SearchFilterValues = {
  driveType?: string;
  primaryDamage?: string;
  titleType?: string;
  fuelType?: string;
  lotCondition?: string;
  odometerRange?: string;
};

export const DRIVE_TYPE_OPTIONS: SearchFilterOption[] = [
  { value: "all_wheel_drive", label: "All Wheel Drive" },
  { value: "front_wheel_drive", label: "Front-wheel Drive" },
  { value: "rear_wheel_drive", label: "Rear-wheel Drive" },
  { value: "4x4_front", label: "4x4 W/front Whl Drv" },
  { value: "4x4_rear", label: "4x4 W/rear Wheel Drv" },
];

export const PRIMARY_DAMAGE_OPTIONS: SearchFilterOption[] = [
  { value: "front_end", label: "Front End" },
  { value: "rear_end", label: "Rear End" },
  { value: "side", label: "Side" },
  { value: "hail", label: "Hail" },
  { value: "minor_dents_scratches", label: "Minor Dents/Scratches" },
  { value: "mechanical", label: "Mechanical" },
  { value: "water_flood", label: "Water/Flood" },
  { value: "rollover", label: "Rollover" },
  { value: "normal_wear", label: "Normal Wear" },
];

export const TITLE_TYPE_OPTIONS: SearchFilterOption[] = [
  { value: "clean_title", label: "Clean Title" },
  { value: "salvage_title", label: "Salvage Title" },
  { value: "non_repairable", label: "Non-Repairable" },
];

export const FUEL_TYPE_OPTIONS: SearchFilterOption[] = [{ value: "electric", label: "Electric" }];

export const LOT_CONDITION_OPTIONS: SearchFilterOption[] = [
  { value: "run_and_drive", label: "Run and Drive" },
  { value: "enhanced_vehicles", label: "Enhanced Vehicles" },
  { value: "engine_start_program", label: "Engine Start Program" },
];

export const ODOMETER_RANGE_OPTIONS: SearchFilterOption[] = [
  { value: "under_25000", label: "Under 25,000 mi" },
  { value: "25000_to_50000", label: "25,000 to 50,000 mi" },
  { value: "50001_to_75000", label: "50,001 to 75,000 mi" },
  { value: "75001_to_100000", label: "75,001 to 100,000 mi" },
  { value: "100001_to_150000", label: "100,001 to 150,000 mi" },
  { value: "150001_to_200000", label: "150,001 to 200,000 mi" },
  { value: "over_200000", label: "Over 200,000 mi" },
];

function getOptionLabel(options: SearchFilterOption[], value?: string): string | null {
  return options.find((option) => option.value === value)?.label ?? null;
}

export function getDriveTypeLabel(value?: string): string | null {
  return getOptionLabel(DRIVE_TYPE_OPTIONS, value);
}

export function getPrimaryDamageLabel(value?: string): string | null {
  return getOptionLabel(PRIMARY_DAMAGE_OPTIONS, value);
}

export function getTitleTypeLabel(value?: string): string | null {
  return getOptionLabel(TITLE_TYPE_OPTIONS, value);
}

export function getFuelTypeLabel(value?: string): string | null {
  return getOptionLabel(FUEL_TYPE_OPTIONS, value);
}

export function getLotConditionLabel(value?: string): string | null {
  return getOptionLabel(LOT_CONDITION_OPTIONS, value);
}

export function getOdometerRangeLabel(value?: string): string | null {
  return getOptionLabel(ODOMETER_RANGE_OPTIONS, value);
}

export function getSearchFilterLabels(filters: SearchFilterValues): string[] {
  return [
    getDriveTypeLabel(filters.driveType),
    getPrimaryDamageLabel(filters.primaryDamage),
    getTitleTypeLabel(filters.titleType),
    getFuelTypeLabel(filters.fuelType),
    getLotConditionLabel(filters.lotCondition),
    getOdometerRangeLabel(filters.odometerRange),
  ].filter((value): value is string => Boolean(value));
}
