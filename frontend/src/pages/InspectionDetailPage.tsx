import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { TopBar } from "@/components/TopBar";
import { ComplianceStamp } from "@/components/ComplianceStamp";
import { DeclarationTable } from "@/components/DeclarationTable";
import { RuleResultList } from "@/components/RuleResultCard";
import { getInspection, downloadPdfReport, downloadEditableReport } from "@/api/inspections";
import type { Inspection } from "@/types";

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function InspectionDetailPage() {
  const { id } = useParams();
  const [inspection, setInspection] = useState<Inspection | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    getInspection(id).then(setInspection).catch(() => setError("Could not load this inspection."));
  }, [id]);

  if (error) return <div className="app-content"><div className="empty-state">{error}</div></div>;
  if (!inspection) return <div className="app-content">Loading…</div>;

  return (
    <>
      <TopBar title={`Inspection ${inspection.id}`} />
      <div className="app-content">
        <div className="panel" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <h2 style={{ fontSize: 20 }}>{inspection.productName}</h2>
            <p style={{ fontSize: 13, color: "var(--color-steel)" }}>
              {inspection.brand} · Inspector {inspection.inspectorName} ·{" "}
              {new Date(inspection.createdAt).toLocaleString()}
            </p>
          </div>
          <ComplianceStamp status={inspection.status} />
        </div>

        <div className="panel">
          <div className="panel-title">
            Reports
          </div>
          <div style={{ display: "flex", gap: 12 }}>
            <button
              className="btn"
              onClick={async () => triggerDownload(await downloadPdfReport(inspection.id), `${inspection.id}.pdf`)}
            >
              Generate PDF
            </button>
            <button
              className="btn secondary"
              onClick={async () => triggerDownload(await downloadEditableReport(inspection.id), `${inspection.id}.docx`)}
            >
              Export Editable Report
            </button>
            <Link className="btn secondary" to={`/inspections/${inspection.id}/evidence`} style={{ textDecoration: "none" }}>
              Open Evidence Viewer
            </Link>
          </div>
        </div>

        <div className="panel">
          <div className="panel-title">Captured Evidence</div>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            {inspection.images.map((img) => (
              <div key={img.slot} style={{ width: 140 }}>
                <img src={img.dataUrl} alt={img.slot} style={{ width: "100%", border: "1px solid var(--color-line)" }} />
                <div style={{ fontSize: 11.5, color: "var(--color-steel)", marginTop: 4 }}>{img.slot}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="panel">
          <div className="panel-title">Mandatory Declarations</div>
          <DeclarationTable declarations={inspection.declarations} />
        </div>

        <div className="panel">
          <div className="panel-title">Rule Compliance</div>
          <RuleResultList results={inspection.ruleResults} />
        </div>

        {inspection.notes && (
          <div className="panel">
            <div className="panel-title">Inspector Notes</div>
            <p>{inspection.notes}</p>
          </div>
        )}
      </div>
    </>
  );
}
