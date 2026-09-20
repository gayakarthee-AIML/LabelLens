import { useAuth } from "@/context/AuthContext";
import { useOffline } from "@/context/OfflineContext";
import { useNavigate } from "react-router-dom";

export function TopBar({ title }: { title: string }) {
  const { user, logout } = useAuth();
  const { isOnline, syncStatus, queue } = useOffline();
  const navigate = useNavigate();
  const pending = queue.filter((q) => q.status === "PENDING" || q.status === "FAILED").length;

  return (
    <header className="topbar">
      <h2 style={{ fontSize: 19 }}>{title}</h2>
      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <span className="status-pill">
          <span
            className={`status-dot ${syncStatus === "syncing" ? "syncing" : isOnline ? "online" : "offline"}`}
          />
          {syncStatus === "syncing" ? "Syncing…" : isOnline ? "Online" : "Offline"}
          {pending > 0 && ` · ${pending} pending`}
        </span>
        <span className="who">
          Signed in as <strong>{user?.fullName}</strong>
        </span>
        <button
          className="btn secondary"
          style={{ padding: "6px 12px", fontSize: 13 }}
          onClick={async () => {
            await logout();
            navigate("/login");
          }}
        >
          Sign out
        </button>
      </div>
    </header>
  );
}
