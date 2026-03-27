import { FormEvent, useEffect, useMemo, useState } from "react";

import type { ProviderConnection } from "../../types";
import { AsyncStatus } from "../shared/AsyncStatus";

type Props = {
  providerLabel: string;
  credentialLabel: string;
  connection: ProviderConnection | null;
  isLoading: boolean;
  loadError: string | null;
  isBrowserOffline: boolean;
  onConnect: (payload: { username: string; password: string }) => Promise<void>;
  onReconnect: (payload: { username: string; password: string }) => Promise<void>;
  onDisconnect: () => Promise<void>;
};

function getConnectionTone(status: ProviderConnection["status"] | "missing"): "live" | "cached" | "warning" | "danger" {
  switch (status) {
    case "connected":
      return "live";
    case "expiring":
      return "warning";
    case "reconnect_required":
    case "error":
      return "danger";
    default:
      return "cached";
  }
}

function getConnectionLabel(status: ProviderConnection["status"] | "missing"): string {
  switch (status) {
    case "connected":
      return "Connected";
    case "expiring":
      return "Expiring soon";
    case "reconnect_required":
      return "Reconnect required";
    case "disconnected":
      return "Disconnected";
    case "error":
      return "Error";
    default:
      return "Not connected";
  }
}

function formatTimestamp(value: string | null): string {
  if (!value) {
    return "Not available";
  }
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function ProviderConnectionCard({
  providerLabel,
  credentialLabel,
  connection,
  isLoading,
  loadError,
  isBrowserOffline,
  onConnect,
  onReconnect,
  onDisconnect,
}: Props) {
  const [username, setUsername] = useState(connection?.account_label ?? "");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isDisconnecting, setIsDisconnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const status = connection?.status ?? "missing";
  const isConnected = connection?.status === "connected";
  const requiresReconnect = connection?.status === "reconnect_required";
  const canSubmit = username.trim().length > 0 && password.trim().length > 0 && !isBrowserOffline && !isLoading;

  useEffect(() => {
    setUsername(connection?.account_label ?? "");
  }, [connection?.account_label]);

  const helperText = useMemo(() => {
    if (isBrowserOffline) {
      return "Connector changes are unavailable while this device is offline.";
    }
    if (!connection) {
      return `Connect your ${providerLabel} account to enable live search and watchlist refreshes.`;
    }
    if (requiresReconnect) {
      return `${providerLabel} rejected the stored session. Re-enter credentials to restore live actions.`;
    }
    if (connection.status === "expiring") {
      return "This session still works, but it is close to expiry.";
    }
    if (connection.status === "connected") {
      return `Live ${providerLabel} requests use the stored connector bundle. Password is not kept after bootstrap.`;
    }
    return "Connector metadata is available, but live access is not ready.";
  }, [connection, isBrowserOffline, providerLabel, requiresReconnect]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit) {
      return;
    }
    setError(null);
    setNotice(null);
    setIsSubmitting(true);
    try {
      if (requiresReconnect) {
        await onReconnect({ username: username.trim(), password: password.trim() });
        setNotice(`${providerLabel} connection restored.`);
      } else {
        await onConnect({ username: username.trim(), password: password.trim() });
        setNotice(`${providerLabel} connected.`);
      }
      setPassword("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : `Could not update ${providerLabel} connection.`);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleDisconnect() {
    setError(null);
    setNotice(null);
    setIsDisconnecting(true);
    try {
      await onDisconnect();
      setPassword("");
      setNotice(`${providerLabel} connection removed.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : `Could not disconnect ${providerLabel}.`);
    } finally {
      setIsDisconnecting(false);
    }
  }

  return (
    <section className="settings-section settings-section--card provider-connection-card" aria-label={`${providerLabel} connection`}>
      <div className="provider-connection-card__header">
        <div>
          <p className="detail-label">{providerLabel} connector</p>
          <p className="provider-connection-card__status-value">{helperText}</p>
        </div>
        <span className={`status-pill status-pill--${getConnectionTone(status)}`}>{getConnectionLabel(status)}</span>
      </div>

      {loadError ? <AsyncStatus tone="error" compact message={loadError} className="panel-status" /> : null}
      {error ? <AsyncStatus tone="error" compact message={error} className="panel-status" /> : null}
      {notice ? <AsyncStatus tone="success" compact message={notice} className="panel-status" /> : null}

      <dl className="detail-grid detail-grid--single">
        <div className="detail-item detail-item--stack">
          <dt className="detail-label">Account</dt>
          <dd className="detail-value">{connection?.account_label ?? "Not connected"}</dd>
        </div>
        <div className="detail-item detail-item--stack">
          <dt className="detail-label">Connected since</dt>
          <dd className="detail-value">{formatTimestamp(connection?.connected_at ?? null)}</dd>
        </div>
        <div className="detail-item detail-item--stack">
          <dt className="detail-label">Last verified</dt>
          <dd className="detail-value">{formatTimestamp(connection?.last_verified_at ?? null)}</dd>
        </div>
        <div className="detail-item detail-item--stack">
          <dt className="detail-label">Session expiry</dt>
          <dd className="detail-value">{formatTimestamp(connection?.expires_at ?? null)}</dd>
        </div>
      </dl>

      {isConnected ? (
        <div className="provider-connection-card__actions">
          {connection && connection.status !== "disconnected" ? (
            <button
              type="button"
              className="ghost-button"
              onClick={() => void handleDisconnect()}
              disabled={isDisconnecting || isSubmitting}
              aria-busy={isDisconnecting}
            >
              {isDisconnecting ? "Disconnecting..." : "Disconnect"}
            </button>
          ) : null}
        </div>
      ) : (
        <form className="provider-connection-card__form" onSubmit={handleSubmit}>
          <label className="provider-connection-card__field">
            {credentialLabel}
            <input
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="username"
              placeholder="you@example.com"
              disabled={isLoading || isSubmitting || isDisconnecting}
            />
          </label>
          <label className="provider-connection-card__field">
            {providerLabel} password
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              placeholder="••••••••"
              disabled={isLoading || isSubmitting || isDisconnecting}
            />
          </label>
          <div className="provider-connection-card__actions">
            <button type="submit" disabled={!canSubmit || isSubmitting} aria-busy={isSubmitting}>
              {isSubmitting ? "Submitting..." : requiresReconnect ? `Reconnect ${providerLabel}` : `Connect ${providerLabel}`}
            </button>
            {connection && connection.status !== "disconnected" ? (
              <button
                type="button"
                className="ghost-button"
                onClick={() => void handleDisconnect()}
                disabled={isDisconnecting || isSubmitting}
                aria-busy={isDisconnecting}
              >
                {isDisconnecting ? "Disconnecting..." : "Disconnect"}
              </button>
            ) : null}
          </div>
        </form>
      )}
    </section>
  );
}
