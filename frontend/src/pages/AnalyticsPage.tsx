import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { TopBar } from "@/components/TopBar";
import { StatCard } from "@/components/StatCard";
import { fetchAnalytics } from "@/api/dashboard";
import type { AnalyticsSummary } from "@/types";

export function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsSummary | null>(null);

  useEffect(() => {
    fetchAnalytics().then(setData).catch(() => {});
  }, []);

  if (!data) {
    return (
      <>
        <TopBar title="Analytics" />
        <div className="app-content">
          <div className="empty-state">No analytics available yet, or the backend is unreachable.</div>
        </div>
      </>
    );
  }

  return (
    <>
      <TopBar title="Analytics" />
      <div className="app-content">
        <div className="stat-grid">
          <StatCard label="Total Inspections" value={data.totalInspections} />
          <StatCard label="Manual Review Rate" value={`${Math.round(data.manualReviewRate * 100)}%`} />
          <StatCard label="Barcode Mismatch Rate" value={`${Math.round(data.barcodeMismatchRate * 100)}%`} />
          <StatCard label="Avg. OCR Confidence" value={`${Math.round(data.averageOcrConfidence * 100)}%`} />
        </div>

        <div className="panel">
          <div className="panel-title">Most Common Rule Violations</div>
          {data.commonViolations.length === 0 ? (
            <div className="empty-state">No violations recorded yet.</div>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={data.commonViolations} layout="vertical" margin={{ left: 40 }}>
                <CartesianGrid stroke="var(--color-line)" strokeDasharray="3 3" />
                <XAxis type="number" tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="rule" tick={{ fontSize: 10.5 }} width={220} />
                <Tooltip />
                <Bar dataKey="count" fill="#a6373b" />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="panel">
          <div className="panel-title">Inspections by Category</div>
          <table className="data-table">
            <thead><tr><th>Category</th><th>Count</th></tr></thead>
            <tbody>
              {data.inspectionsByCategory.map((c) => (
                <tr key={c.category}><td>{c.category}</td><td className="mono">{c.count}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
