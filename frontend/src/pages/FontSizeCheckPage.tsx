import { useState } from "react";
import { TopBar } from "@/components/TopBar";
import { CameraCapture } from "@/components/CameraCapture";
import { checkFontSize } from "@/api/fontSize";
import { isBackendUnreachable } from "@/api/client";
import type { FontSizeCheckResult } from "@/types";

// This page is intentionally its own screen behind its own nav item/button
// — font size checking (Rule 8, via a reference-card calibration) is a
// distinct workflow from OCR-based declaration extraction, not a step
// inside it. See backend/app/services/font_size_service.py.
export function FontSizeCheckPage() {
  const [cardWidthMm, setCardWidthMm] = useState(85.6);
  const [cardHeightMm, setCardHeightMm] = useState(53.98);
  const [result, setResult] = useState<FontSizeCheckResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasCapture, setHasCapture] = useState(false);

  const runCheck = async (dataUrl: string) => {
    setHasCapture(true);
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const res = await checkFontSize(dataUrl, { cardWidthMm, cardHeightMm });
      setResult(res);
    } catch (err) {
      if (isBackendUnreachable(err)) {
        setError(
          "Font size checking needs a live connection to the backend (card detection and OCR run " +
            "server-side) — this device appears to be offline. Try again once connectivity returns."
        );
      } else {
        setError("Could not process this photo. Retake it with the card fully visible and try again.");
      }
    } finally {
      setBusy(false);
    }
  };

  const reset = () => {
    setHasCapture(false);
    setResult(null);
    setError(null);
  };

  return (
    <>
      <TopBar title="Font Size Check" />
      <div className="app-content">
        <div className="panel">
          <div className="panel-title">How this works</div>
          <p style={{ fontSize: 13, color: "var(--color-steel)" }}>
            Place a standard reference card (e.g. a debit/credit/Aadhaar-style ID-1 card) flat on the
            package, right next to the declaration you want to check, so both are visible in one photo.
            The app uses the card's known real-world size to convert the printed text's pixel height
            into millimetres, then compares it against the configured minimum height for that
            declaration (Rule 8 of the Legal Metrology (Packaged Commodities) Rules, 2011). This check is
            independent of the OCR/compliance analysis run during an inspection.
          </p>
          <div className="field-row">
            <div className="field">
              <label>Reference card width (mm)</label>
              <input
                type="number"
                step="0.01"
                value={cardWidthMm}
                onChange={(e) => setCardWidthMm(Number(e.target.value))}
              />
            </div>
            <div className="field">
              <label>Reference card height (mm)</label>
              <input
                type="number"
                step="0.01"
                value={cardHeightMm}
                onChange={(e) => setCardHeightMm(Number(e.target.value))}
              />
            </div>
          </div>
          <p style={{ fontSize: 12, color: "var(--color-steel)" }}>
            Defaults are the ISO/IEC 7810 ID-1 card size (85.60mm × 53.98mm) — most bank cards and
            Aadhaar cards. Change these only if using a different, precisely-sized reference object.
          </p>
        </div>

        <div className="panel">
          <div className="panel-title">Capture</div>
          {!hasCapture || error ? (
            <CameraCapture
              guidanceLabel="Frame the reference card and the declaration text together, flat and well-lit."
              onCapture={(dataUrl) => runCheck(dataUrl)}
            />
          ) : busy ? (
            <p>Detecting reference card and measuring text height…</p>
          ) : (
            <button className="btn secondary" type="button" onClick={reset}>
              Check another photo
            </button>
          )}
          {error && <p style={{ color: "var(--color-violation-red)", marginTop: 12 }}>{error}</p>}
        </div>

        {result && (
          <div className="panel">
            <div className="panel-title" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span>Result</span>
              <span className={`badge ${result.overallStatus.toLowerCase()}`}>
                {result.overallStatus.replace(/_/g, " ")}
              </span>
            </div>

            {!result.card.found ? (
              <p style={{ color: "var(--color-violation-red)" }}>{result.card.message}</p>
            ) : (
              <>
                <p style={{ fontSize: 13, color: "var(--color-steel)" }}>
                  {result.card.message} Calibration confidence: {Math.round(result.card.confidence * 100)}%
                  {" · "}
                  {result.card.pxPerMm?.toFixed(2)} px/mm
                </p>
                {result.measurements.length === 0 ? (
                  <div className="empty-state">No legible text was detected in this photo.</div>
                ) : (
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Detected Text</th>
                        <th>Matched Standard</th>
                        <th>Measured Height</th>
                        <th>Required Height</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.measurements.map((m, i) => (
                        <tr key={i}>
                          <td className="mono">{m.text}</td>
                          <td>{m.standardName ?? "—"}</td>
                          <td className="mono">{m.heightMm.toFixed(2)} mm</td>
                          <td className="mono">{m.requiredMm != null ? `${m.requiredMm.toFixed(2)} mm` : "—"}</td>
                          <td>
                            <span className={`badge ${m.status.toLowerCase()}`}>{m.status}</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </>
  );
}
