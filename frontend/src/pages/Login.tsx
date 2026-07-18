import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import type { Role } from "../types";

export default function Login() {
  const { login, register } = useAuth();
  const nav = useNavigate();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<Role>("employee");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const user = mode === "login" ? await login(email, password) : await register(email, password, role);
      nav(user.role === "agent" ? "/dashboard" : "/tickets");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-wrap">
      <form className="card auth-card" onSubmit={submit}>
        <h1>⚡ QuickDesk</h1>
        <p className="muted">AI-assisted internal helpdesk</p>
        <label>
          Email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />
        </label>
        <label>
          Password
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} />
        </label>
        {mode === "register" && (
          <label>
            Role
            <select value={role} onChange={(e) => setRole(e.target.value as Role)}>
              <option value="employee">Employee</option>
              <option value="agent">Agent</option>
            </select>
          </label>
        )}
        {error && <p className="error">{error}</p>}
        <button disabled={busy}>{busy ? "…" : mode === "login" ? "Log in" : "Create account"}</button>
        <p className="muted center">
          {mode === "login" ? "No account?" : "Already registered?"}{" "}
          <a href="#" onClick={(e) => { e.preventDefault(); setMode(mode === "login" ? "register" : "login"); setError(""); }}>
            {mode === "login" ? "Register" : "Log in"}
          </a>
        </p>
        <p className="muted center small">
          Seeded demo users: agent@quickdesk.io / agentpass123 · employee@quickdesk.io / employeepass123
        </p>
      </form>
    </div>
  );
}
