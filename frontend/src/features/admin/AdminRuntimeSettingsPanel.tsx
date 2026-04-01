import { useEffect, useMemo, useState } from "react";

import type { AdminRuntimeSetting, AdminRuntimeSettingsGroup, AdminRuntimeSettingUpdate } from "../../types";
import { AsyncStatus } from "../shared/AsyncStatus";

type Props = {
  groups: AdminRuntimeSettingsGroup[];
  isLoading: boolean;
  isSaving: boolean;
  error: string | null;
  onRetry: () => Promise<void>;
  onSave: (updates: AdminRuntimeSettingUpdate[]) => Promise<void>;
  onReset: (keys: string[]) => Promise<void>;
};

function formatValue(value: number | number[]): string {
  return Array.isArray(value) ? value.join(", ") : String(value);
}

function formatBounds(setting: AdminRuntimeSetting): string | null {
  if (setting.value_type === "integer") {
    if (setting.min_value !== null && setting.max_value !== null) {
      return `${setting.min_value}-${setting.max_value} ${setting.unit ?? ""}`.trim();
    }
    if (setting.min_value !== null) {
      return `>= ${setting.min_value} ${setting.unit ?? ""}`.trim();
    }
    if (setting.max_value !== null) {
      return `<= ${setting.max_value} ${setting.unit ?? ""}`.trim();
    }
    return null;
  }
  const parts: string[] = [];
  if (setting.min_items !== null || setting.max_items !== null) {
    parts.push(
      setting.min_items !== null && setting.max_items !== null
        ? `${setting.min_items}-${setting.max_items} values`
        : setting.min_items !== null
          ? `at least ${setting.min_items} value(s)`
          : `at most ${setting.max_items} value(s)`,
    );
  }
  if (setting.min_value !== null || setting.max_value !== null) {
    parts.push(
      setting.min_value !== null && setting.max_value !== null
        ? `${setting.min_value}-${setting.max_value} ${setting.unit ?? ""}`.trim()
        : setting.min_value !== null
          ? `>= ${setting.min_value} ${setting.unit ?? ""}`.trim()
          : `<= ${setting.max_value} ${setting.unit ?? ""}`.trim(),
    );
  }
  return parts.length > 0 ? parts.join(" · ") : null;
}

function validateDraft(setting: AdminRuntimeSetting, rawValue: string): AdminRuntimeSettingUpdate {
  if (setting.value_type === "integer") {
    const parsed = Number.parseInt(rawValue.trim(), 10);
    if (Number.isNaN(parsed)) {
      throw new Error(`${setting.label} requires a whole number.`);
    }
    if (setting.min_value !== null && parsed < setting.min_value) {
      throw new Error(`${setting.label} must be at least ${setting.min_value}.`);
    }
    if (setting.max_value !== null && parsed > setting.max_value) {
      throw new Error(`${setting.label} cannot exceed ${setting.max_value}.`);
    }
    return { key: setting.key, value: parsed };
  }

  const parsedValues = rawValue
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => {
      const parsed = Number.parseInt(item, 10);
      if (Number.isNaN(parsed)) {
        throw new Error(`${setting.label} requires comma-separated whole numbers.`);
      }
      return parsed;
    });

  const normalizedValues = Array.from(new Set(parsedValues)).sort((left, right) => right - left);
  if (setting.min_items !== null && normalizedValues.length < setting.min_items) {
    throw new Error(`${setting.label} requires at least ${setting.min_items} value(s).`);
  }
  if (setting.max_items !== null && normalizedValues.length > setting.max_items) {
    throw new Error(`${setting.label} allows at most ${setting.max_items} value(s).`);
  }
  for (const value of normalizedValues) {
    if (setting.min_value !== null && value < setting.min_value) {
      throw new Error(`${setting.label} cannot contain values below ${setting.min_value}.`);
    }
    if (setting.max_value !== null && value > setting.max_value) {
      throw new Error(`${setting.label} cannot contain values above ${setting.max_value}.`);
    }
  }
  return { key: setting.key, value: normalizedValues };
}

export function AdminRuntimeSettingsPanel({ groups, isLoading, isSaving, error, onRetry, onSave, onReset }: Props) {
  const [draftValues, setDraftValues] = useState<Record<string, string>>({});
  const [localMessage, setLocalMessage] = useState<string | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const items = useMemo(() => groups.flatMap((group) => group.items), [groups]);

  useEffect(() => {
    const nextDrafts: Record<string, string> = {};
    for (const item of items) {
      nextDrafts[item.key] = formatValue(item.effective_value);
    }
    setDraftValues(nextDrafts);
  }, [items]);

  const dirtyKeys = items.filter((item) => draftValues[item.key] !== formatValue(item.effective_value)).map((item) => item.key);

  async function handleSave() {
    setLocalMessage(null);
    setLocalError(null);
    if (dirtyKeys.length === 0) {
      setLocalMessage("No runtime changes to save.");
      return;
    }
    try {
      const updates = items
        .filter((item) => dirtyKeys.includes(item.key))
        .map((item) => validateDraft(item, draftValues[item.key] ?? formatValue(item.effective_value)));
      await onSave(updates);
      setLocalMessage("Runtime settings saved.");
    } catch (caught) {
      setLocalError(caught instanceof Error ? caught.message : "Couldn't save runtime settings.");
    }
  }

  async function handleReset(key: string) {
    setLocalMessage(null);
    setLocalError(null);
    try {
      await onReset([key]);
      setLocalMessage("Runtime setting reset to default.");
    } catch (caught) {
      setLocalError(caught instanceof Error ? caught.message : "Couldn't reset runtime setting.");
    }
  }

  return (
    <section className="panel panel--support admin-runtime-settings-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Admin</p>
          <h2>Runtime Settings</h2>
          <p className="panel-header__lede">Safe polling, freshness, retry, and invite knobs that apply without a deploy.</p>
        </div>
        <div className="admin-runtime-settings-panel__actions">
          <button type="button" className="ghost-button" onClick={() => void onRetry()} disabled={isLoading || isSaving}>
            Reload
          </button>
          <button type="button" onClick={() => void handleSave()} disabled={isLoading || isSaving} aria-busy={isSaving}>
            {isSaving ? "Saving..." : "Save Runtime Settings"}
          </button>
        </div>
      </div>

      {isLoading && groups.length === 0 ? (
        <AsyncStatus
          progress="spinner"
          title="Loading runtime settings"
          message="Getting current effective values and admin overrides."
          className="panel-status"
        />
      ) : null}

      {error ? (
        <AsyncStatus
          tone="error"
          title="Couldn't load runtime settings"
          message={error}
          action={
            <button type="button" className="ghost-button" onClick={() => void onRetry()}>
              Try again
            </button>
          }
          className="panel-status"
        />
      ) : null}

      {localError ? <AsyncStatus tone="error" message={localError} className="panel-status" /> : null}
      {localMessage ? <AsyncStatus compact tone="success" message={localMessage} className="panel-status" /> : null}

      <div className="admin-runtime-settings-groups" aria-label="Runtime settings groups">
        {groups.map((group) => (
          <section key={group.key} className="admin-runtime-settings-group" aria-label={group.label}>
            <div className="admin-runtime-settings-group__header">
              <p className="eyebrow">{group.label}</p>
            </div>
            <div className="admin-runtime-settings-list">
              {group.items.map((setting) => {
                const draftValue = draftValues[setting.key] ?? formatValue(setting.effective_value);
                const bounds = formatBounds(setting);
                const isDirty = draftValue !== formatValue(setting.effective_value);
                return (
                  <article key={setting.key} className="admin-runtime-setting-card">
                    <div className="admin-runtime-setting-card__header">
                      <div>
                        <h3>{setting.label}</h3>
                        <p className="muted">{setting.description}</p>
                      </div>
                      <button
                        type="button"
                        className="ghost-button"
                        onClick={() => void handleReset(setting.key)}
                        disabled={isSaving || !setting.is_overridden}
                        aria-label={`Reset ${setting.label}`}
                      >
                        Reset
                      </button>
                    </div>
                    <label className="admin-runtime-setting-card__field">
                      <span className="sr-only">{setting.label}</span>
                      <input
                        type="text"
                        value={draftValue}
                        onChange={(event) =>
                          setDraftValues((current) => ({
                            ...current,
                            [setting.key]: event.target.value,
                          }))
                        }
                        inputMode={setting.value_type === "integer" ? "numeric" : "text"}
                        aria-label={setting.label}
                      />
                    </label>
                    <dl className="admin-runtime-setting-card__meta">
                      <div>
                        <dt>Effective</dt>
                        <dd>{formatValue(setting.effective_value)}</dd>
                      </div>
                      <div>
                        <dt>Default</dt>
                        <dd>{formatValue(setting.default_value)}</dd>
                      </div>
                      {bounds ? (
                        <div>
                          <dt>Bounds</dt>
                          <dd>{bounds}</dd>
                        </div>
                      ) : null}
                      {setting.updated_at ? (
                        <div>
                          <dt>Updated</dt>
                          <dd>{new Date(setting.updated_at).toLocaleString()}</dd>
                        </div>
                      ) : null}
                    </dl>
                    {isDirty ? <p className="admin-runtime-setting-card__dirty">Unsaved change</p> : null}
                  </article>
                );
              })}
            </div>
          </section>
        ))}
      </div>
    </section>
  );
}
