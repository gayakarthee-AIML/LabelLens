import { useEffect, useState } from "react";
import { TopBar } from "@/components/TopBar";
import { listUsers, createUser, updateUser } from "@/api/users";
import { ROLE_LABELS } from "@/api/auth";
import type { UserRecord, UserRole } from "@/types";

const ROLES: UserRole[] = ["INSPECTOR", "SENIOR_INSPECTOR", "ADMINISTRATOR", "REGULATOR"];

export function UserManagementPage() {
  const [users, setUsers] = useState<UserRecord[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [officialId, setOfficialId] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState<UserRole>("INSPECTOR");
  const [password, setPassword] = useState("");
  const [jurisdiction, setJurisdiction] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = () => listUsers().then(setUsers).catch(() => setError("Could not load users."));

  useEffect(() => {
    load();
  }, []);

  const handleCreate = async () => {
    setError(null);
    try {
      await createUser({ officialId, fullName, role, password, jurisdiction: jurisdiction || undefined });
      setShowForm(false);
      setOfficialId("");
      setFullName("");
      setPassword("");
      setJurisdiction("");
      load();
    } catch (err: any) {
      setError(err?.message || "Could not create user.");
    }
  };

  const toggleActive = async (user: UserRecord) => {
    await updateUser(user.id, { isActive: !user.isActive });
    load();
  };

  const changeRole = async (user: UserRecord, newRole: UserRole) => {
    await updateUser(user.id, { role: newRole });
    load();
  };

  return (
    <>
      <TopBar title="User Management" />
      <div className="app-content">
        <div className="panel">
          <div className="panel-title">
            Accounts
            <button className="btn secondary" style={{ padding: "6px 14px", fontSize: 13 }} onClick={() => setShowForm((s) => !s)}>
              {showForm ? "Cancel" : "Add User"}
            </button>
          </div>

          {showForm && (
            <div style={{ border: "1px solid var(--color-line)", padding: 16, marginBottom: 16 }}>
              <div className="field">
                <label>Official ID</label>
                <input value={officialId} onChange={(e) => setOfficialId(e.target.value)} />
              </div>
              <div className="field">
                <label>Full name</label>
                <input value={fullName} onChange={(e) => setFullName(e.target.value)} />
              </div>
              <div className="field">
                <label>Role</label>
                <select value={role} onChange={(e) => setRole(e.target.value as UserRole)}>
                  {ROLES.map((r) => (
                    <option key={r} value={r}>{ROLE_LABELS[r]}</option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label>Jurisdiction (optional)</label>
                <input value={jurisdiction} onChange={(e) => setJurisdiction(e.target.value)} />
              </div>
              <div className="field">
                <label>Temporary password</label>
                <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
              </div>
              {error && <p style={{ color: "var(--color-violation-red)", fontSize: 13 }}>{error}</p>}
              <button className="btn" onClick={handleCreate} disabled={!officialId || !fullName || !password}>
                Create Account
              </button>
            </div>
          )}

          <table className="data-table">
            <thead>
              <tr>
                <th>Official ID</th>
                <th>Name</th>
                <th>Role</th>
                <th>Jurisdiction</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td className="mono">{u.officialId}</td>
                  <td>{u.fullName}</td>
                  <td>
                    <select value={u.role} onChange={(e) => changeRole(u, e.target.value as UserRole)}>
                      {ROLES.map((r) => (
                        <option key={r} value={r}>{ROLE_LABELS[r]}</option>
                      ))}
                    </select>
                  </td>
                  <td>{u.jurisdiction ?? "—"}</td>
                  <td>{u.isActive ? "Active" : "Deactivated"}</td>
                  <td>
                    <button
                      className="btn secondary"
                      style={{ padding: "4px 10px", fontSize: 12 }}
                      onClick={() => toggleActive(u)}
                    >
                      {u.isActive ? "Deactivate" : "Reactivate"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
