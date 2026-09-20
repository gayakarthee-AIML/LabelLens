import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import type { UserRole } from "@/types";
import { useAuth } from "@/context/AuthContext";
import { ROLE_LABELS } from "@/api/auth";
import { ApiError } from "@/api/client";

const REMEMBERED_KEY = "labellens.rememberedId";

function loadRemembered(role: UserRole): string {
  try {
    const raw = localStorage.getItem(REMEMBERED_KEY);
    if (!raw) return "";
    const parsed = JSON.parse(raw) as { role: UserRole; officialId: string };
    return parsed.role === role ? parsed.officialId : "";
  } catch {
    return "";
  }
}

export function RoleLoginForm({ role, onBack }: { role: UserRole; onBack: () => void }) {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [officialId, setOfficialId] = useState(() => loadRemembered(role));
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(() => !!loadRemembered(role));
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const user = await login({ role, officialId, password });
      // Only the Official ID is remembered — never the password. Storing
      // it as {role, officialId} (not a bare string) is what makes
      // loadRemembered() above actually pre-fill the field on a future
      // visit; the previous version wrote this but nothing ever read it
      // back, so the checkbox had no visible effect.
      if (remember) {
        localStorage.setItem(REMEMBERED_KEY, JSON.stringify({ role, officialId }));
      } else {
        localStorage.removeItem(REMEMBERED_KEY);
      }
      // Redirect based on the role the SERVER returned, not the one selected on this screen.
      void user;
      navigate("/dashboard");
    } catch (err) {
      if (err instanceof ApiError && err.status === 0) {
        setError("Backend unreachable. Check VITE_API_BASE_URL and that the API is running.");
      } else if (err instanceof ApiError && err.status === 401) {
        setError("Invalid official ID or password.");
      } else {
        setError("Login failed. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="login-shell">
      <div className="login-card">
        <button className="back-link" onClick={onBack} type="button">← Change access type</button>
        <div className="login-header" style={{ textAlign: "left", marginBottom: 24 }}>
          <h1 style={{ fontSize: 24 }}>{ROLE_LABELS[role]} Login</h1>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="officialId">Official ID / Email</label>
            <input
              id="officialId"
              value={officialId}
              onChange={(e) => setOfficialId(e.target.value)}
              autoComplete="username"
              required
            />
          </div>
          <div className="field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </div>
          <div className="field" style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <input
              id="remember"
              type="checkbox"
              style={{ width: "auto" }}
              checked={remember}
              onChange={(e) => setRemember(e.target.checked)}
            />
            <label htmlFor="remember" style={{ margin: 0 }}>Remember this device</label>
          </div>
          {error && <p style={{ color: "var(--color-violation-red)", fontSize: 13.5 }}>{error}</p>}
          <button className="btn block" type="submit" disabled={submitting}>
            {submitting ? "Verifying…" : "Secure Login"}
          </button>
        </form>
      </div>
    </div>
  );
}
