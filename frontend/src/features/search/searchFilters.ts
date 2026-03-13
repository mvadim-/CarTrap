export type SearchFilterOption = {
  label: string;
  value: string;
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

export function getDriveTypeLabel(value?: string): string | null {
  return DRIVE_TYPE_OPTIONS.find((option) => option.value === value)?.label ?? null;
}

export function getPrimaryDamageLabel(value?: string): string | null {
  return PRIMARY_DAMAGE_OPTIONS.find((option) => option.value === value)?.label ?? null;
}
