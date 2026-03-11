import { FormEvent, useState } from "react";

import type { Invite } from "../../types";

type Props = {
  inviteLink: string | null;
  onCreateInvite: (email: string) => Promise<Invite>;
};

export function AdminInvitesPanel({ inviteLink, onCreateInvite }: Props) {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const invite = await onCreateInvite(email);
    setMessage(`Invite created for ${invite.email}`);
    setEmail("");
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Admin</p>
          <h2>Generate Invites</h2>
        </div>
      </div>
      <form className="inline-form" onSubmit={handleSubmit}>
        <input
          aria-label="Invite email"
          placeholder="buyer@auctiondesk.com"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          type="email"
          required
        />
        <button type="submit">Create Invite</button>
      </form>
      {message ? <p className="success">{message}</p> : null}
      {inviteLink ? (
        <div className="callout">
          <span>Latest invite link</span>
          <a href={inviteLink}>{inviteLink}</a>
        </div>
      ) : (
        <p className="muted">No invites generated in this session.</p>
      )}
    </section>
  );
}
