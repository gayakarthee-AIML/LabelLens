import { useEffect, useState } from "react";
import { TopBar } from "@/components/TopBar";
import { fetchEnforcementOverview } from "@/api/dashboard";
import { StatCard } from "@/components/StatCard";

interface EnforcementOverview {
  violationsBySeverity: { severity: string; count: number }[];
  repeatViolators: { manufacturer: string; violationCount: number }[];
  unresolvedFindings: number;
  pendingReviews: number;
}

export function EnforcementPage() {
  const [data, setData] = useState<EnforcementOverview | null>(null);

  useEffect(() => {
    fetchEnforcementOverview().then((d) => setData(d as EnforcementOverview)).catch(() => {});
  }, []);

  return (
    <>
      <TopBar title="Enforcement Monitoring" />
      <div className="app-content">
        {!data ? (
          <div className="empty-state">
            No enforcement data available yet, or the backend is unreachable.
          </div>
        ) : (
          <>
            <div className="stat-grid">
              <StatCard label="Unresolved Findings" value={data.unresolvedFindings} />
              <StatCard label="Pending Reviews" value={data.pendingReviews} />
            </div>
            <div className="panel">
              <div className="panel-title">Violations by Severity</div>
              <table className="data-table">
                <thead><tr><th>Severity</th><th>Count</th></tr></thead>
                <tbody>
                  {data.violationsBySeverity.map((v) => (
                    <tr key={v.severity}><td>{v.severity}</td><td className="mono">{v.count}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="panel">
              <div className="panel-title">Repeat Violators</div>
              <table className="data-table">
                <thead><tr><th>Manufacturer</th><th>Violation Count</th></tr></thead>
                <tbody>
                  {data.repeatViolators.map((r) => (
                    <tr key={r.manufacturer}><td>{r.manufacturer}</td><td className="mono">{r.violationCount}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </>
  );
}
