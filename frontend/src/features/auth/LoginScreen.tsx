import { FormEvent, useState } from "react";

type Props = {
  error: string | null;
  onSubmit: (email: string, password: string) => Promise<void>;
};

export function LoginScreen({ error, onSubmit }: Props) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    try {
      await onSubmit(email, password);
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="panel auth-panel">
      <p className="eyebrow">Invite-Only Access</p>
      <h1>Track Copart lots before the rest of the yard reacts.</h1>
      <p className="lede">
        Log in to manage watchlists, run manual searches, send push alerts, and coordinate auction activity.
      </p>
      <form className="stack" onSubmit={handleSubmit}>
        <label>
          Email
          <input
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            type="email"
            autoComplete="email"
            autoCapitalize="off"
            autoCorrect="off"
            inputMode="email"
            spellCheck={false}
            required
          />
        </label>
        <label>
          Password
          <input
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            type="password"
            autoComplete="current-password"
            required
          />
        </label>
        {error ? <p className="error">{error}</p> : null}
        <button type="submit" disabled={pending}>
          {pending ? "Signing In..." : "Sign In"}
        </button>
      </form>
      <p className="muted">
        Need an invite? Ask your{" "}
        <a
          href="mailto:vpm2000@gmail.com?subject=CarTrap%20invite%20request&body=Hello%2C%20please%20send%20me%20an%20invite%20link%20for%20CarTrap."
        >
          administrator
        </a>{" "}
        for an invite link.
      </p>
    </section>
  );
}
