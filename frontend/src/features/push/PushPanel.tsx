import type { PushSubscriptionItem } from "../../types";

type Props = {
  subscriptions: PushSubscriptionItem[];
  permissionState: string;
  onSubscribe: () => Promise<void>;
  onUnsubscribe: (endpoint: string) => Promise<void>;
};

export function PushPanel({ subscriptions, permissionState, onSubscribe, onUnsubscribe }: Props) {
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Push</p>
          <h2>Browser Notifications</h2>
        </div>
        <span className="status-pill">{permissionState}</span>
      </div>
      <button type="button" onClick={onSubscribe}>
        Enable Push On This Device
      </button>
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
