import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

import type { ProviderConnection, PushDeliveryResult, PushSubscriptionConfig, PushSubscriptionItem } from "../../types";
import { CopartConnectionCard } from "../integrations/CopartConnectionCard";
import { ProviderConnectionCard } from "../integrations/ProviderConnectionCard";
import { AsyncStatus } from "../shared/AsyncStatus";
import { shouldUseMobileFullscreen } from "../shared/mobileFullscreen";
import { useBodyScrollLock } from "../shared/useBodyScrollLock";

type Props = {
  isOpen: boolean;
  isAdmin: boolean;
  providerConnectionsError: string | null;
  copartConnection: ProviderConnection | null;
  iaaiConnection: ProviderConnection | null;
  isLoadingProviderConnections: boolean;
  subscriptions: PushSubscriptionItem[];
  subscriptionsError: string | null;
  isLoadingSubscriptions: boolean;
  pushConfig: PushSubscriptionConfig | null;
  pushConfigError: string | null;
  isLoadingPushConfig: boolean;
  currentDeviceEndpoint: string | null;
  permissionState: string;
  supportsPush: boolean;
  isSecureContext: boolean;
  isBrowserOffline: boolean;
  isSubscribing: boolean;
  unsubscribingEndpoint: string | null;
  isSendingTestPush: boolean;
  onConnectCopart: (payload: { username: string; password: string }) => Promise<void>;
  onReconnectCopart: (payload: { username: string; password: string }) => Promise<void>;
  onDisconnectCopart: () => Promise<void>;
  onConnectIaai: (payload: { username: string; password: string }) => Promise<void>;
  onReconnectIaai: (payload: { username: string; password: string }) => Promise<void>;
  onDisconnectIaai: () => Promise<void>;
  onRetryDiagnostics: () => Promise<void>;
  onSubscribe: () => Promise<PushSubscriptionItem>;
  onUnsubscribe: (endpoint: string) => Promise<void>;
  onSendTestPush: () => Promise<PushDeliveryResult>;
  onClose: () => void;
};

function formatTimestamp(value: string | null): string {
  if (!value) {
    return "—";
  }
  return new Date(value).toLocaleString();
}

function maskEndpoint(endpoint: string): string {
  const maxLength = 52;
  if (endpoint.length <= maxLength) {
    return endpoint;
  }
  return `${endpoint.slice(0, 28)}...${endpoint.slice(-18)}`;
}

export function PushSettingsModal({
  isOpen,
  isAdmin,
  providerConnectionsError,
  copartConnection,
  iaaiConnection,
  isLoadingProviderConnections,
  subscriptions,
  subscriptionsError,
  isLoadingSubscriptions,
  pushConfig,
  pushConfigError,
  isLoadingPushConfig,
  currentDeviceEndpoint,
  permissionState,
  supportsPush,
  isSecureContext,
  isBrowserOffline,
  isSubscribing,
  unsubscribingEndpoint,
  isSendingTestPush,
  onConnectCopart,
  onReconnectCopart,
  onDisconnectCopart,
  onConnectIaai,
  onReconnectIaai,
  onDisconnectIaai,
  onRetryDiagnostics,
  onSubscribe,
  onUnsubscribe,
  onSendTestPush,
  onClose,
}: Props) {
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const isMobileFullscreen = shouldUseMobileFullscreen();

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

  async function handleSubscribe() {
    setMessage(null);
    setError(null);
    try {
      await onSubscribe();
      setMessage("Push is enabled for this device.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not enable push notifications.");
    }
  }

  async function handleUnsubscribe(endpoint: string) {
    setMessage(null);
    setError(null);
    try {
      await onUnsubscribe(endpoint);
      setMessage("Push subscription revoked.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not revoke push subscription.");
    }
  }

  async function handleSendTest() {
    setMessage(null);
    setError(null);
    try {
      const result = await onSendTestPush();
      setMessage(
        `Push test finished: ${result.delivered} delivered, ${result.failed} failed, ${result.removed} removed.`,
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not send test push.");
    }
  }

  const serverStatus = pushConfig
    ? pushConfig.enabled && pushConfig.public_key
      ? "Configured"
      : pushConfig.reason ?? "Not configured"
    : isLoadingPushConfig
      ? "Loading diagnostics"
      : "Unknown";

  const modal = (
    <div
      className={`modal-backdrop${isMobileFullscreen ? " modal-backdrop--mobile-screen" : ""}`}
      onClick={onClose}
    >
      <div
        aria-label="Settings"
        aria-modal="true"
        className={`modal-card settings-modal${isMobileFullscreen ? " modal-card--mobile-screen settings-modal--mobile" : ""}`}
        role="dialog"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header settings-modal__header">
          <div>
            <p className="eyebrow">Settings</p>
            <h3>User Preferences</h3>
          </div>
          <button type="button" className="ghost-button" onClick={onClose}>
            Close
          </button>
        </div>
        <div className="modal-body settings-modal__body">
          <section className="settings-section" aria-label="Connector settings">
            <div className="panel-header">
              <div>
                <p className="eyebrow">Connectors</p>
                <h3>Auction Accounts</h3>
              </div>
            </div>
            <p className="muted settings-section__intro">
              Manage the live Copart and IAAI sessions this device uses for search and watchlist refreshes.
            </p>
            <CopartConnectionCard
              connection={copartConnection}
              isLoading={isLoadingProviderConnections}
              loadError={providerConnectionsError}
              isBrowserOffline={isBrowserOffline}
              onConnect={onConnectCopart}
              onReconnect={onReconnectCopart}
              onDisconnect={onDisconnectCopart}
            />
            <ProviderConnectionCard
              providerLabel="IAAI"
              credentialLabel="IAAI email"
              connection={iaaiConnection}
              isLoading={isLoadingProviderConnections}
              loadError={providerConnectionsError}
              isBrowserOffline={isBrowserOffline}
              onConnect={onConnectIaai}
              onReconnect={onReconnectIaai}
              onDisconnect={onDisconnectIaai}
            />
          </section>
          <section className="settings-section settings-section--card">
            <div className="panel-header">
              <div>
                <p className="eyebrow">Push</p>
                <h3>Browser Notifications</h3>
              </div>
              {isAdmin ? (
                <button type="button" className="ghost-button" onClick={() => void onRetryDiagnostics()}>
                  Retry Diagnostics
                </button>
              ) : null}
            </div>
            {isBrowserOffline ? (
              <AsyncStatus
                compact
                tone="error"
                title="Device offline"
                message={
                  isAdmin
                    ? "Reconnect to refresh diagnostics, enable push, or send a test notification."
                    : "Reconnect to enable push or manage device subscriptions."
                }
                className="panel-status"
              />
            ) : null}
            {isAdmin && (isLoadingPushConfig || isLoadingSubscriptions) ? (
              <AsyncStatus
                compact
                progress="bar"
                title="Loading push diagnostics"
                message="Checking browser support, server readiness, and registered device subscriptions."
                className="panel-status"
              />
            ) : null}
            {isAdmin && pushConfigError ? (
              <AsyncStatus
                compact
                tone="error"
                title="Push diagnostics unavailable"
                message={pushConfigError}
                className="panel-status"
              />
            ) : null}
            {subscriptionsError ? (
              <AsyncStatus
                compact
                tone="error"
                title="Device list unavailable"
                message={subscriptionsError}
                className="panel-status"
              />
            ) : null}
            {error ? <AsyncStatus compact tone="error" message={error} className="panel-status" /> : null}
            {message ? <AsyncStatus compact tone="success" message={message} className="panel-status" /> : null}
            <dl className="detail-grid detail-grid--single">
              <div className="detail-item">
                <dt className="detail-label">Permission:</dt>
                <dd className="detail-value">
                  <span className="status-pill">{permissionState}</span>
                </dd>
              </div>
              <div className="detail-item">
                <dt className="detail-label">Subscriptions:</dt>
                <dd className="detail-value">{subscriptions.length}</dd>
              </div>
              {isAdmin ? (
                <>
                  <div className="detail-item">
                    <dt className="detail-label">Browser support:</dt>
                    <dd className="detail-value">{supportsPush ? "Supported" : "Unsupported"}</dd>
                  </div>
                  <div className="detail-item">
                    <dt className="detail-label">Secure context:</dt>
                    <dd className="detail-value">{isSecureContext ? "Ready" : "HTTPS or localhost required"}</dd>
                  </div>
                  <div className="detail-item detail-item--stack">
                    <dt className="detail-label">Server config:</dt>
                    <dd className="detail-value">{serverStatus}</dd>
                  </div>
                  <div className="detail-item detail-item--stack">
                    <dt className="detail-label">Current device:</dt>
                    <dd className="detail-value">{currentDeviceEndpoint ? "Registered" : "Not registered here"}</dd>
                  </div>
                </>
              ) : null}
            </dl>
            <div className="settings-section__actions">
              <button type="button" onClick={() => void handleSubscribe()} disabled={isSubscribing} aria-busy={isSubscribing}>
                {isSubscribing ? "Enabling..." : "Enable Push On This Device"}
              </button>
              {isAdmin ? (
                <button
                  type="button"
                  className="ghost-button"
                  onClick={() => void handleSendTest()}
                  disabled={isSendingTestPush}
                  aria-busy={isSendingTestPush}
                >
                  {isSendingTestPush ? "Sending Test..." : "Send Test Push"}
                </button>
              ) : null}
            </div>
            {subscriptions.length === 0 && !isLoadingSubscriptions ? (
              <p className="muted">No device subscriptions registered.</p>
            ) : (
              <div className="result-list">
                {subscriptions.map((subscription) => {
                  const isCurrentDevice = currentDeviceEndpoint === subscription.endpoint;
                  return (
                    <article key={subscription.id} className="result-card result-card--support push-subscription-card">
                      <div className="push-subscription-card__copy">
                        <strong className="push-subscription-card__title">
                          {isAdmin && isCurrentDevice ? "This browser" : subscription.user_agent ?? "Browser Subscription"}
                        </strong>
                        <p className="muted push-subscription-card__endpoint">{maskEndpoint(subscription.endpoint)}</p>
                        <p className="muted">Updated {formatTimestamp(subscription.updated_at)}</p>
                      </div>
                      <button
                        type="button"
                        className="ghost-button push-subscription-card__action"
                        onClick={() => void handleUnsubscribe(subscription.endpoint)}
                        disabled={unsubscribingEndpoint === subscription.endpoint}
                        aria-busy={unsubscribingEndpoint === subscription.endpoint}
                      >
                        {unsubscribingEndpoint === subscription.endpoint ? "Revoking..." : "Revoke"}
                      </button>
                    </article>
                  );
                })}
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );

  return typeof document !== "undefined" ? createPortal(modal, document.body) : modal;
}
