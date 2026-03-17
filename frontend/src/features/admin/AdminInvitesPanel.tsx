import { FormEvent, useState } from "react";

import type { Invite } from "../../types";
import { AsyncStatus } from "../shared/AsyncStatus";

type Props = {
  inviteLink: string | null;
  latestInvite: Invite | null;
  isCreatingInvite: boolean;
  onCreateInvite: (email: string) => Promise<Invite>;
};

function formatTimestamp(value: string | null): string {
  if (!value) {
    return "—";
  }
  return new Date(value).toLocaleString();
}

export function AdminInvitesPanel({ inviteLink, latestInvite, isCreatingInvite, onCreateInvite }: Props) {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage(null);
    setError(null);
    try {
      const invite = await onCreateInvite(email);
      setMessage(`Invite created for ${invite.email}`);
      setEmail("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not create invite.");
    }
  }

  async function handleCopyInviteLink() {
    if (!inviteLink || !navigator.clipboard) {
      setMessage("Copy the link manually from the panel below.");
      return;
    }
    await navigator.clipboard.writeText(inviteLink);
    setMessage("Invite link copied.");
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Admin</p>
          <h2>Generate Invites</h2>
        </div>
      </div>
      {error ? <AsyncStatus tone="error" title="Invite creation failed" message={error} className="panel-status" /> : null}
      {message ? <AsyncStatus compact tone="success" message={message} className="panel-status" /> : null}
      <form className="inline-form" onSubmit={handleSubmit} aria-busy={isCreatingInvite}>
        <input
          aria-label="Invite email"
          placeholder="buyer@auctiondesk.com"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          type="email"
          required
        />
        <button type="submit" disabled={isCreatingInvite} aria-busy={isCreatingInvite}>
          {isCreatingInvite ? "Creating..." : "Create Invite"}
        </button>
      </form>
      {isCreatingInvite ? (
        <AsyncStatus
          compact
          progress="bar"
          title="Creating invite"
          message="The invite token and support link will appear here when ready."
          className="panel-status"
        />
      ) : null}
      {latestInvite ? (
        <dl className="detail-grid detail-grid--single admin-panel__details">
          <div className="detail-item">
            <dt className="detail-label">Latest invite:</dt>
            <dd className="detail-value">{latestInvite.email}</dd>
          </div>
          <div className="detail-item">
            <dt className="detail-label">Status:</dt>
            <dd className="detail-value">{latestInvite.status}</dd>
          </div>
          <div className="detail-item detail-item--stack">
            <dt className="detail-label">Expires:</dt>
            <dd className="detail-value">{formatTimestamp(latestInvite.expires_at)}</dd>
          </div>
        </dl>
      ) : null}
      {inviteLink ? (
        <div className="callout">
          <span>Latest invite link</span>
          <a href={inviteLink}>{inviteLink}</a>
          <button type="button" className="ghost-button" onClick={() => void handleCopyInviteLink()}>
            Copy Link
          </button>
        </div>
      ) : (
        <p className="muted">No invites generated in this session.</p>
      )}
    </section>
  );
}
