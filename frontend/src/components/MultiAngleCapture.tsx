import { useState } from "react";
import { CameraCapture } from "./CameraCapture";
import type { CapturedImage, ImageSlot } from "@/types";

const PACKAGE_REQUIRED_ANGLES: { slot: ImageSlot; label: string; guidance: string }[] = [
  { slot: "front", label: "Front", guidance: "Frame the front label. Ensure product name and MRP are visible." },
  { slot: "back", label: "Back", guidance: "Capture the back panel — ingredients, manufacturer, and net quantity." },
  { slot: "left", label: "Left Side", guidance: "Capture the left side panel for any additional declarations." },
  { slot: "right", label: "Right Side", guidance: "Capture the right side panel for any additional declarations." }
];

// Label mode is a singular scan, not a 4-side capture — an inspector
// checking just the label only needs the panel(s) the declarations are
// actually printed on, not the whole package's physical condition. Front is
// the only required shot; Back is offered but optional since many labels
// split declarations across front/back.
const LABEL_REQUIRED_ANGLES: { slot: ImageSlot; label: string; guidance: string }[] = [
  { slot: "front", label: "Label", guidance: "Frame the full label panel. Ensure all printed text is sharp and in focus." }
];
const LABEL_OPTIONAL_ANGLES: { slot: ImageSlot; label: string; guidance: string }[] = [
  { slot: "back", label: "Back (if separate)", guidance: "Capture the back panel only if declarations continue there." }
];

// Barcode/QR capture is only required for electronic products, per the
// brief — appended to the required set conditionally in the component
// below, not scanned/cross-checked for any other category (see
// backend/app/api/routers/inspections.py, Settings.is_electronic_category).
const BARCODE_ANGLE: { slot: ImageSlot; label: string; guidance: string } = {
  slot: "barcode",
  label: "Barcode / QR",
  guidance: "Fill the frame with the barcode or QR code. Hold steady for a sharp capture."
};

const PACKAGE_OPTIONAL_ANGLES: { slot: ImageSlot; label: string; guidance: string }[] = [
  { slot: "top", label: "Top", guidance: "Capture the top of the package, if it carries any declaration." },
  { slot: "bottom", label: "Bottom", guidance: "Capture the bottom of the package, if it carries any declaration." },
  { slot: "additional", label: "Additional Evidence", guidance: "Capture any other supporting evidence." }
];

export function MultiAngleCapture({
  images,
  onImagesChange,
  requireBarcode = true,
  mode = "PACKAGE"
}: {
  images: CapturedImage[];
  onImagesChange: (images: CapturedImage[]) => void;
  /** Only electronic products require/scan a barcode or QR code, per the brief. */
  requireBarcode?: boolean;
  /** PACKAGE requires all 4 sides; LABEL is a singular scan (front only, back optional). */
  mode?: "PACKAGE" | "LABEL";
}) {
  const baseRequired = mode === "LABEL" ? LABEL_REQUIRED_ANGLES : PACKAGE_REQUIRED_ANGLES;
  const baseOptional = mode === "LABEL" ? LABEL_OPTIONAL_ANGLES : PACKAGE_OPTIONAL_ANGLES;
  const requiredAngles = requireBarcode ? [...baseRequired, BARCODE_ANGLE] : baseRequired;
  const allAngles = [...requiredAngles, ...baseOptional];
  const firstIncomplete = allAngles.find((a) => !images.some((i) => i.slot === a.slot));
  const [activeSlot, setActiveSlot] = useState<ImageSlot>(firstIncomplete?.slot ?? "front");

  const activeAngle = allAngles.find((a) => a.slot === activeSlot)!;
  const capturedForActive = images.find((i) => i.slot === activeSlot);

  const handleCapture = (dataUrl: string, quality: { flags: string[] }) => {
    const captured: CapturedImage = {
      slot: activeSlot,
      dataUrl,
      capturedAt: new Date().toISOString(),
      qualityFlags: quality.flags,
      uploaded: false
    };
    const next = [...images.filter((i) => i.slot !== activeSlot), captured];
    onImagesChange(next);

    const nextIncomplete = allAngles.find(
      (a) => a.slot !== activeSlot && !next.some((i) => i.slot === a.slot)
    );
    if (nextIncomplete) setActiveSlot(nextIncomplete.slot);
  };

  const requiredDone = requiredAngles.every((a) => images.some((i) => i.slot === a.slot));

  return (
    <div>
      <div className="capture-shell">
        <div className="angle-list">
          {allAngles.map((a) => {
            const done = images.some((i) => i.slot === a.slot);
            return (
              <button
                key={a.slot}
                type="button"
                className={`angle-item ${activeSlot === a.slot ? "active" : ""} ${done ? "done" : ""}`}
                onClick={() => setActiveSlot(a.slot)}
              >
                <span>{a.label}</span>
                <span>{done ? "✓" : "○"}</span>
              </button>
            );
          })}
        </div>

        <div>
          {capturedForActive ? (
            <div>
              <div className="camera-frame">
                <img src={capturedForActive.dataUrl} alt={`${activeAngle.label} capture`} />
              </div>
              {capturedForActive.qualityFlags.length > 0 && (
                <div className="quality-flags">
                  {capturedForActive.qualityFlags.map((f) => (
                    <span className="quality-flag" key={f}>{f.replace(/_/g, " ")}</span>
                  ))}
                </div>
              )}
              <div className="camera-actions">
                <button
                  className="btn secondary"
                  type="button"
                  onClick={() => onImagesChange(images.filter((i) => i.slot !== activeSlot))}
                >
                  Retake {activeAngle.label}
                </button>
              </div>
            </div>
          ) : (
            <CameraCapture guidanceLabel={activeAngle.guidance} onCapture={handleCapture} />
          )}
        </div>
      </div>

      {!requiredDone && (
        <p style={{ fontSize: 12.5, color: "var(--color-steel)", marginTop: 12 }}>
          {mode === "LABEL"
            ? requireBarcode
              ? "The label panel and Barcode/QR are required before analysis can run."
              : "The label panel is required before analysis can run."
            : requireBarcode
            ? "Front, Back, Left Side, Right Side, and Barcode/QR are required before analysis can run."
            : "Front, Back, Left Side, and Right Side are required before analysis can run. Barcode/QR " +
              "capture only applies to electronic products."}
        </p>
      )}
    </div>
  );
}
