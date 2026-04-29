import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { Button, Input } from "../components/ui";
import { RssIcon } from "../components/icons";

type LoginPageProps = {
  onLogin: () => void;
};

export default function LoginPage({ onLogin }: LoginPageProps) {
  const navigate = useNavigate();
  const [token, setToken] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.login(token);
      onLogin();
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-page">
      <div className="card login-card">
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
          <RssIcon width={22} height={22} style={{ color: "var(--accent)" }} />
          <span style={{ fontSize: 15, fontWeight: 510, color: "var(--text-primary)" }}>Own New Newsletter</span>
        </div>
        <h1>Sign in</h1>
        <p>Enter your admin token to access the panel.</p>
        <form onSubmit={submit}>
          <div className="field">
            <span className="field-label">Admin token</span>
            <Input
              value={token}
              onChange={(e) => setToken(e.target.value)}
              type="password"
              placeholder="Paste your token"
              autoFocus
              required
            />
            <span className="field-hint">Stored as an HttpOnly session cookie after login.</span>
          </div>
          {error ? <div className="error-msg">{error}</div> : null}
          <Button disabled={busy || !token} style={{ width: "100%" }}>
            {busy ? "Signing in..." : "Sign in"}
          </Button>
        </form>
      </div>
    </div>
  );
}
