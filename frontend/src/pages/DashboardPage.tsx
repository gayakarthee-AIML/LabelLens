import { useEffect, useState } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  BarChart,
  Bar
} from "recharts";
import { fetchDashboardSummary } from "@/api/dashboard";
import { searchInspections } from "@/api/inspections";
import { isBackendUnreachable } from "@/api/client";
import { TopBar } from "@/components/TopBar";
import { StatCard } from "@/components/StatCard";
import { ComplianceStamp } from "@/components/ComplianceStamp";
import type { DashboardSummary, Inspection } from "@/types";
import { Link } from "react-router-dom";

export function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [recent, setRecent] = useState<Inspection[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchDashboardSummary()
      .then(setSummary)
      .catch((err) => setError(isBackendUnreachable(err) ? "BACKEND_UNREACHABLE" : "ERROR"));
    searchInspections({ pageSize: 8 })
      .then((res) => setRecent(res.items))
      .catch(() => {});
  }, []);

  return (
    <>
      <TopBar title="Compliance Dashboard" />
      <div className="app-content">
        {error === "BACKEND_UNREACHABLE" && (
          <div className="empty-state" style={{ marginBottom: 24 }}>
            Cannot reach the LabelLens API at the configured VITE_API_BASE_URL. Start the
            backend (see backend/README.md) and reload — dashboard figures come from live
            inspection data, not placeholders.
          </div>
        )}

        {summary && (
          <>
            <div className="stat-grid">
              <StatCard label="Total Inspections" value={summary.totalInspections} />
              <StatCard label="Today's Inspections" value={summary.todayInspections} />
              <StatCard label="Compliant" value={summary.compliant} />
              <StatCard label="Non-Compliant" value={summary.nonCompliant} />
              <StatCard label="Review Required" value={summary.reviewRequired} />
              <StatCard label="Violations Detected" value={summary.violationsDetected} />
              <StatCard label="Pending Reviews" value={summary.pendingReviews} />
              <StatCard label="Offline Pending Sync" value={summary.pendingSync} />
            </div>

            <div className="panel">
              <div className="panel-title">Compliance Trend</div>
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={summary.complianceTrend}>
                  <CartesianGrid stroke="var(--color-line)" strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="compliant" stroke="#2e6f40" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="nonCompliant" stroke="#a6373b" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="review" stroke="#b9812b" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>

            <div className="panel">
              <div className="panel-title">Violations by Category</div>
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={summary.violationsByCategory}>
                  <CartesianGrid stroke="var(--color-line)" strokeDasharray="3 3" />
                  <XAxis dataKey="category" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="count" fill="#16213e" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </>
        )}

        <div className="panel">
          <div className="panel-title">Recent Inspections</div>
          {recent.length === 0 ? (
            <div className="empty-state">No inspections recorded yet.</div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Product</th>
                  <th>Barcode</th>
                  <th>Inspector</th>
                  <th>Date</th>
                  <th>Status</th>
                  <th>Report</th>
                </tr>
              </thead>
              <tbody>
                {recent.map((i) => (
                  <tr key={i.id}>
                    <td>{i.productName}</td>
                    <td className="mono">{i.barcode?.rawValue ?? "—"}</td>
                    <td>{i.inspectorName}</td>
                    <td className="mono">{new Date(i.createdAt).toLocaleDateString()}</td>
                    <td><ComplianceStamp status={i.status} /></td>
                    <td><Link to={`/inspections/${i.id}`}>View</Link></td>
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
