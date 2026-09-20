import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { TopBar } from "@/components/TopBar";
import { getEvidence, addEvidenceNote } from "@/api/inspections";
import type { EvidenceBundle, EvidenceImage } from "@/types";

function OverlayImage({ image, showOriginal }: { image: EvidenceImage; showOriginal: boolean }) {
  const imgRef = useRef<HTMLImageElement>(null);
  const [naturalSize, setNaturalSize] = useState<{ w: number; h: number } | null>(null);
  const src = showOriginal || !image.processedUrl ? image.originalUrl : image.processedUrl;

  return (
    <div style={{ position: "relative", display: "inline-block", maxWidth: "100%" }}>
      <img
        ref={imgRef}
        src={src}
        alt={`${image.slot} evidence`}
        style={{ maxWidth: "100%", display: "block", border: "1px solid var(--color-line)" }}
        onLoad={(e) => {
          const el = e.currentTarget;
          setNaturalSize({ w: el.naturalWidth, h: el.naturalHeight });
        }}
      />
      {/* OCR bounding-box overlay. Boxes are in the pixel space of the image
          PaddleOCR actually ran on (see backend/app/services/ocr_service.py) —
          positioned here as percentages so they track the rendered image size.
          Note: if YOLO cropped a sub-region before OCR, box coordinates are
          relative to that crop, not the full image — an offset this overlay
          does not yet correct for. It matches exactly when no trained YOLO
          model is present (the documented fallback: full frame == full crop). */}
      {!showOriginal &&
        naturalSize &&
        image.ocrWords.map((word, idx) => {
          const xs = word.box.map((p) => p[0]);
          const ys = word.box.map((p) => p[1]);
          const x = Math.min(...xs);
          const y = Math.min(...ys);
          const w = Math.max(...xs) - x;
          const h = Math.max(...ys) - y;
          return (
            <div
              key={idx}
              title={`${word.text} (${Math.round(word.confidence * 100)}%)`}
              style={{
                position: "absolute",
                left: `${(x / naturalSize.w) * 100}%`,
                top: `${(y / naturalSize.h) * 100}%`,
                width: `${(w / naturalSize.w) * 100}%`,
                height: `${(h / naturalSize.h) * 100}%`,
                border: `1.5px solid ${word.confidence > 0.7 ? "#2e6f40" : "#b9812b"}`,
                boxSizing: "border-box"
              }}
            />
          );
        })}
    </div>
  );
}

export function EvidenceViewerPage() {
  const { id } = useParams();
  const [bundle, setBundle] = useState<EvidenceBundle | null>(null);
  const [activeSlot, setActiveSlot] = useState<string | null>(null);
  const [showOriginal, setShowOriginal] = useState(false);
  const [noteDraft, setNoteDraft] = useState("");
  const [saving, setSaving] = useState(false);

  const load = () => {
    if (!id) return;
    getEvidence(id).then((b) => {
      setBundle(b);
      if (!activeSlot && b.images.length > 0) setActiveSlot(b.images[0].slot);
    });
  };

  useEffect(load, [id]);

  const activeImage = bundle?.images.find((i) => i.slot === activeSlot) ?? null;

  useEffect(() => {
    setNoteDraft(activeImage?.note ?? "");
  }, [activeImage?.remoteImageId]);

  const saveNote = async () => {
    if (!id || !activeImage) return;
    setSaving(true);
    try {
      await addEvidenceNote(id, activeImage.remoteImageId, noteDraft);
      load();
    } finally {
      setSaving(false);
    }
  };

  if (!bundle) return <div className="app-content">Loading evidence…</div>;

  return (
    <>
      <TopBar title="Evidence Viewer" />
      <div className="app-content">
        <div className="capture-shell">
          <div className="angle-list">
            {bundle.images.map((img) => (
              <button
                key={img.slot}
                type="button"
                className={`angle-item ${activeSlot === img.slot ? "active" : ""}`}
                onClick={() => setActiveSlot(img.slot)}
              >
                <span style={{ textTransform: "capitalize" }}>{img.slot}</span>
                <span>{img.quality.flags.length > 0 ? "⚠" : "✓"}</span>
              </button>
            ))}
          </div>

          {activeImage && (
            <div>
              <div className="camera-actions" style={{ marginTop: 0, marginBottom: 12 }}>
                <button className="btn secondary" onClick={() => setShowOriginal(false)} disabled={!showOriginal}>
                  Processed + OCR overlay
                </button>
                <button className="btn secondary" onClick={() => setShowOriginal(true)} disabled={showOriginal}>
                  Original
                </button>
              </div>

              <OverlayImage image={activeImage} showOriginal={showOriginal} />

              <div className="panel" style={{ marginTop: 16 }}>
                <div className="panel-title">Image Quality</div>
                <p style={{ fontSize: 13 }}>
                  Brightness: <span className="mono">{activeImage.quality.brightness?.toFixed(1) ?? "—"}</span> ·
                  Blur score: <span className="mono">{activeImage.quality.blurScore?.toFixed(1) ?? "—"}</span> ·
                  Glare: <span className="mono">{activeImage.quality.glarePct ? `${Math.round(activeImage.quality.glarePct * 100)}%` : "—"}</span>
                </p>
                {activeImage.quality.flags.length > 0 && (
                  <div className="quality-flags">
                    {activeImage.quality.flags.map((f) => (
                      <span className="quality-flag" key={f}>{f.replace(/_/g, " ")}</span>
                    ))}
                  </div>
                )}
              </div>

              <div className="panel">
                <div className="panel-title">Add Evidence Note</div>
                <div className="field">
                  <textarea
                    value={noteDraft}
                    onChange={(e) => setNoteDraft(e.target.value)}
                    rows={3}
                    style={{ width: "100%", padding: 10, border: "1px solid var(--color-line)", fontFamily: "inherit" }}
                  />
                </div>
                <button className="btn" onClick={saveNote} disabled={saving}>
                  Save Note
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
