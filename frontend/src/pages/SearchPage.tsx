import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { TopBar } from "@/components/TopBar";
import { ComplianceStamp } from "@/components/ComplianceStamp";
import { searchInspections } from "@/api/inspections";
import type { Inspection } from "@/types";

export function SearchPage() {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [results, setResults] = useState<Inspection[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);

  const runSearch = async () => {
    setLoading(true);
    try {
      const res = await searchInspections({ query, status: status || undefined, pageSize: 25 });
      setResults(res.items);
      setTotal(res.total);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void runSearch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <>
      <TopBar title="Search & Repository" />
      <div className="app-content">
        <div className="toolbar">
          <input
            placeholder="Product, brand, manufacturer, barcode, inspector, or inspection ID"
            style={{ minWidth: 340 }}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && runSearch()}
          />
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All statuses</option>
            <option value="COMPLIANT">Compliant</option>
            <option value="NON_COMPLIANT">Non-Compliant</option>
            <option value="REVIEW_REQUIRED">Review Required</option>
          </select>
          <button className="btn" onClick={runSearch} disabled={loading}>Search</button>
        </div>

        <div className="panel">
          <div className="panel-title">
            Results <span style={{ fontSize: 12.5, color: "var(--color-steel)", fontFamily: "var(--font-mono)" }}>{total} total</span>
          </div>
          {results.length === 0 ? (
            <div className="empty-state">No matching inspections.</div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Product</th>
                  <th>Barcode</th>
                  <th>Inspector</th>
                  <th>Location</th>
                  <th>Date</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {results.map((r) => (
                  <tr key={r.id}>
                    <td><Link to={`/inspections/${r.id}`}>{r.productName}</Link></td>
                    <td className="mono">{r.barcode?.rawValue ?? "—"}</td>
                    <td>{r.inspectorName}</td>
                    <td>{r.location ?? "—"}</td>
                    <td className="mono">{new Date(r.createdAt).toLocaleDateString()}</td>
                    <td><ComplianceStamp status={r.status} /></td>
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
