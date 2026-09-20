import { useEffect, useRef, useState } from "react";
import { TopBar } from "@/components/TopBar";
import { listRules, toggleRule, exportRules, importRules, ruleUpdateHistory } from "@/api/rules";
import type { ComplianceRule } from "@/types";

export function RuleManagementPage() {
  const [rules, setRules] = useState<ComplianceRule[]>([]);
  const [history, setHistory] = useState<{ version: string; publishedAt: string; source: string; changeSummary: string }[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = async () => {
    setRules(await listRules());
    setHistory(await ruleUpdateHistory());
  };

  useEffect(() => {
    void load();
  }, []);

  const handleExport = async () => {
    const blob = await exportRules();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "labellens-rules.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const result = await importRules(file);
    setMessage(`Imported ${result.imported} rules into version ${result.version}.`);
    await load();
  };

  return (
    <>
      <TopBar title="Rule Management" />
      <div className="app-content">
        <div className="panel">
          <div className="panel-title">
            Government Rule Update
          </div>
          <p style={{ fontSize: 13, color: "var(--color-steel)" }}>
            No live government rule-feed API is currently connected. Rules are maintained through this
            local repository and can be imported from an official JSON/YAML export when one becomes
            available — see the adapter in <code>backend/app/services/rule_engine.py</code>.
          </p>
          <div style={{ display: "flex", gap: 12 }}>
            <button className="btn secondary" onClick={handleExport}>Export current rule set (JSON)</button>
            <button className="btn secondary" onClick={() => fileInputRef.current?.click()}>Import rule set</button>
            <input ref={fileInputRef} type="file" accept=".json,.yaml,.yml" style={{ display: "none" }} onChange={handleImport} />
          </div>
          {message && <p style={{ fontSize: 13, marginTop: 8 }}>{message}</p>}
        </div>

        <div className="panel">
          <div className="panel-title">Rules — Legal Metrology (Packaged Commodities) Rules, 2011</div>
          <table className="data-table">
            <thead>
              <tr>
                <th>Rule ID</th>
                <th>Name</th>
                <th>Category</th>
                <th>Validation</th>
                <th>Severity</th>
                <th>Version</th>
                <th>Effective</th>
                <th>Enabled</th>
              </tr>
            </thead>
            <tbody>
              {rules.map((r) => (
                <tr key={r.ruleId}>
                  <td className="mono">{r.ruleId}</td>
                  <td>{r.name}</td>
                  <td>{r.applicableCategory}</td>
                  <td className="mono">{r.validationType}</td>
                  <td>{r.severity}</td>
                  <td className="mono">v{r.version}</td>
                  <td className="mono">{r.effectiveDate}</td>
                  <td>
                    <button
                      className="btn secondary"
                      style={{ padding: "4px 10px", fontSize: 12 }}
                      onClick={async () => {
                        await toggleRule(r.ruleId, !r.enabled);
                        await load();
                      }}
                    >
                      {r.enabled ? "Enabled" : "Disabled"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="panel">
          <div className="panel-title">Update History</div>
          {history.length === 0 ? (
            <div className="empty-state">No update history recorded yet.</div>
          ) : (
            <table className="data-table">
              <thead><tr><th>Version</th><th>Published</th><th>Source</th><th>Summary</th></tr></thead>
              <tbody>
                {history.map((h) => (
                  <tr key={h.version}>
                    <td className="mono">v{h.version}</td>
                    <td className="mono">{new Date(h.publishedAt).toLocaleDateString()}</td>
                    <td>{h.source}</td>
                    <td>{h.changeSummary}</td>
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
