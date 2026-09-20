import { useEffect, useState } from "react";
import { TopBar } from "@/components/TopBar";
import { useOffline } from "@/context/OfflineContext";
import { listLocalInspections } from "@/services/offlineDb";
import type { Inspection } from "@/types";
import { StatCard } from "@/components/StatCard";

export function OfflineQueuePage() {
  const { queue, isOnline, forceSync, refreshQueue } = useOffline();
  const [local, setLocal] = useState<Inspection[]>([]);

  useEffect(() => {
    listLocalInspections().then(setLocal);
  }, [queue]);

  const synced = local.filter((i) => i.synced).length;
  const pending = local.filter((i) => !i.synced).length;
  const failed = queue.filter((q) => q.status === "FAILED").length;

  return (
    <>
      <TopBar title="Offline Queue" />
      <div className="app-content">
        <div className="stat-grid">
          <StatCard label="Pending Sync" value={pending} />
          <StatCard label="Synced" value={synced} />
          <StatCard label="Failed" value={failed} />
        </div>

        <div className="panel">
          <div className="panel-title">
            Sync Controls
          </div>
          <p style={{ fontSize: 13, color: "var(--color-steel)" }}>
            Inspections captured while offline are stored in this device's IndexedDB. When the
            connection returns they are re-created on the server, images are uploaded, and the full
            OCR/rule-engine pipeline runs — nothing here is a placeholder result.
          </p>
          <button className="btn" disabled={!isOnline} onClick={async () => { await forceSync(); await refreshQueue(); }}>
            {isOnline ? "Sync now" : "Waiting for connection…"}
          </button>
        </div>

        <div className="panel">
          <div className="panel-title">Locally Stored Inspections</div>
          {local.length === 0 ? (
            <div className="empty-state">Nothing stored locally.</div>
          ) : (
            <table className="data-table">
              <thead><tr><th>Product</th><th>Captured</th><th>Images</th><th>Status</th></tr></thead>
              <tbody>
                {local.map((i) => (
                  <tr key={i.id}>
                    <td>{i.productName}</td>
                    <td className="mono">{new Date(i.createdAt).toLocaleString()}</td>
                    <td className="mono">{i.images.length}</td>
                    <td>{i.synced ? "Synced" : "Pending"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </>
  );
}
