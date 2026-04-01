export function formatAdminTimestamp(value: string | null): string {
  if (!value) {
    return "—";
  }
  return new Date(value).toLocaleString();
}

export function formatAdminShortDate(value: string | null): string {
  if (!value) {
    return "—";
  }
  return new Date(value).toLocaleDateString();
}

export function formatAdminCount(value: number): string {
  return new Intl.NumberFormat().format(value);
}

export function formatAdminCurrency(value: number | null, currency = "USD"): string {
  if (value === null || Number.isNaN(value)) {
    return "—";
  }
  return `${new Intl.NumberFormat().format(value)} ${currency}`;
}
