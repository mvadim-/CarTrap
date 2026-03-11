import { FormEvent, useState } from "react";

type Props = {
  inviteToken: string;
  error: string | null;
  onSubmit: (password: string) => Promise<void>;
};

export function InviteAcceptScreen({ inviteToken, error, onSubmit }: Props) {
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    try {
      await onSubmit(password);
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="panel auth-panel">
      <p className="eyebrow">Accept Invite</p>
      <h1>Create your CarTrap password</h1>
      <p className="lede">This invite token will be used one time and then closed.</p>
      <code className="token-preview">{inviteToken}</code>
      <form className="stack" onSubmit={handleSubmit}>
        <label>
          New Password
          <input
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            type="password"
            minLength={8}
            required
          />
        </label>
        {error ? <p className="error">{error}</p> : null}
        <button type="submit" disabled={pending}>
          {pending ? "Activating..." : "Activate Account"}
        </button>
      </form>
    </section>
  );
}
