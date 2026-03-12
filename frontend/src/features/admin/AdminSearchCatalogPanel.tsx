import type { SearchCatalog } from "../../types";

type Props = {
  catalog: SearchCatalog | null;
  onRefresh: () => Promise<void>;
};

function formatTimestamp(value: string | null): string {
  if (!value) {
    return "unknown";
  }
  return new Date(value).toLocaleString();
}

export function AdminSearchCatalogPanel({ catalog, onRefresh }: Props) {
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Admin</p>
          <h2>Search Catalog</h2>
        </div>
      </div>
      <p className="muted">
        {catalog
          ? `${catalog.summary.make_count} makes · ${catalog.summary.assigned_model_count} assigned models · ${catalog.summary.unassigned_model_count} unassigned`
          : "Catalog not loaded yet."}
      </p>
      <p className="muted">Generated: {formatTimestamp(catalog?.generated_at ?? null)}</p>
      <button type="button" onClick={() => void onRefresh()}>
        Refresh Search Catalog
      </button>
    </section>
  );
}
