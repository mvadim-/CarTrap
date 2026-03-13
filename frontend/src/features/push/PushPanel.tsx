import type { PushSubscriptionItem } from "../../types";

type Props = {
  subscriptions: PushSubscriptionItem[];
  permissionState: string;
  onSubscribe: () => Promise<void>;
  onUnsubscribe: (endpoint: string) => Promise<void>;
};

export function PushPanel({ subscriptions, permissionState, onSubscribe, onUnsubscribe }: Props) {
  return (
    <section className="panel push-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Push</p>
          <h2>Browser Notifications</h2>
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
      <div className="push-panel__actions">
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
  );
}
