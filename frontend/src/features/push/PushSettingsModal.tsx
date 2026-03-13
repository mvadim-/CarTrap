import { useEffect } from "react";

import type { PushSubscriptionItem } from "../../types";

type Props = {
  isOpen: boolean;
  subscriptions: PushSubscriptionItem[];
  permissionState: string;
  onSubscribe: () => Promise<void>;
  onUnsubscribe: (endpoint: string) => Promise<void>;
  onClose: () => void;
};

export function PushSettingsModal({
  isOpen,
  subscriptions,
  permissionState,
  onSubscribe,
  onUnsubscribe,
  onClose,
}: Props) {
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
        aria-label="Settings"
        aria-modal="true"
        className="modal-card settings-modal"
        role="dialog"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <p className="eyebrow">Settings</p>
            <h3>User Preferences</h3>
          </div>
          <button type="button" className="ghost-button" onClick={onClose}>
            Close
          </button>
        </div>
        <div className="modal-body settings-modal__body">
          <section className="settings-section">
            <div className="panel-header">
              <div>
                <p className="eyebrow">Push</p>
                <h3>Browser Notifications</h3>
              </div>
            </div>
            <dl className="detail-grid detail-grid--single">
              <div className="detail-item">
                <dt className="detail-label">Status:</dt>
                <dd className="detail-value">
                  <span className="status-pill">{permissionState}</span>
                </dd>
              </div>
              <div className="detail-item detail-item--stack">
                <dt className="detail-label">Subscriptions:</dt>
                <dd className="detail-value">{subscriptions.length}</dd>
              </div>
            </dl>
            <div className="settings-section__actions">
              <button type="button" onClick={onSubscribe}>
                Enable Push On This Device
              </button>
            </div>
            {subscriptions.length === 0 ? (
              <p className="muted">No device subscriptions registered.</p>
            ) : (
              <div className="result-list">
                {subscriptions.map((subscription) => (
                  <article key={subscription.id} className="result-card">
                    <div>
                      <strong>{subscription.user_agent ?? "Browser Subscription"}</strong>
                      <p className="muted">{subscription.endpoint}</p>
                    </div>
                    <button type="button" className="ghost-button" onClick={() => onUnsubscribe(subscription.endpoint)}>
                      Revoke
                    </button>
                  </article>
                ))}
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
