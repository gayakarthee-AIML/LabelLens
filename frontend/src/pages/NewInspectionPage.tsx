import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { v4 as uuid } from "@/services/uuid";
import { TopBar } from "@/components/TopBar";
import { MultiAngleCapture } from "@/components/MultiAngleCapture";
import { SpinCapture } from "@/components/SpinCapture";
import { CameraCapture } from "@/components/CameraCapture";
import { DeclarationTable } from "@/components/DeclarationTable";
import { RuleResultList } from "@/components/RuleResultCard";
import { ComplianceStamp } from "@/components/ComplianceStamp";
import { useAuth } from "@/context/AuthContext";
import { useTranslation } from "@/context/I18nContext";
import type { TranslationKey } from "@/i18n/locales";
import {
  createInspection,
  uploadInspectionImage,
  runAnalysis,
  analyzeEcommerceListing,
  submitHumanVerification,
  finalizeInspection
} from "@/api/inspections";
import { isBackendUnreachable } from "@/api/client";
import { saveInspectionLocally } from "@/services/offlineDb";
import type { CapturedImage, Inspection } from "@/types";

type Step = "DETAILS" | "CAPTURE" | "ECOMMERCE_INPUT" | "PROCESSING" | "RESULT" | "SAVED";
type InspectionMode = "PACKAGE" | "LABEL" | "ECOMMERCE";

// Only these categories require/scan a barcode or QR code, per the brief —
// kept in sync with backend Settings.electronic_categories
// (backend/app/core/config.py).
const ELECTRONIC_CATEGORIES = new Set(["Electronics", "Electronics Accessory", "Electronic Appliance"]);

function getModes(t: (key: TranslationKey) => string): { id: InspectionMode; icon: string; label: string; blurb: string }[] {
  return [
    { id: "PACKAGE", icon: "📦", label: t("inspection.mode.package.label"), blurb: t("inspection.mode.package.blurb") },
    { id: "LABEL", icon: "🏷️", label: t("inspection.mode.label.label"), blurb: t("inspection.mode.label.blurb") },
    { id: "ECOMMERCE", icon: "🌐", label: t("inspection.mode.ecommerce.label"), blurb: t("inspection.mode.ecommerce.blurb") }
  ];
}

export function NewInspectionPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const MODES = getModes(t);

  const [step, setStep] = useState<Step>("DETAILS");
  const [mode, setMode] = useState<InspectionMode>("PACKAGE");
  const [productName, setProductName] = useState("");
  const [brand, setBrand] = useState("");
  const [category, setCategory] = useState("Packaged Food");
  const [images, setImages] = useState<CapturedImage[]>([]);
  const [useSpinScan, setUseSpinScan] = useState(false);
  const [listingUrl, setListingUrl] = useState("");
  const [inspection, setInspection] = useState<Inspection | null>(null);
  const [verifiedProductName, setVerifiedProductName] = useState("");
  const [verifiedBrand, setVerifiedBrand] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const isElectronic = ELECTRONIC_CATEGORIES.has(category);
  const requiredSlots =
    mode === "LABEL"
      ? isElectronic
        ? ["front", "barcode"]
        : ["front"]
      : isElectronic
      ? ["front", "back", "left", "right", "barcode"]
      : ["front", "back", "left", "right"];
  const spinPrefix = `${mode === "LABEL" ? "label" : "package"}_spin`;
  const captureComplete = useSpinScan
    ? images.some((i) => i.slot.startsWith(spinPrefix)) && (!isElectronic || images.some((i) => i.slot === "barcode"))
    : requiredSlots.every((s) => images.some((i) => i.slot === s));

  const buildOfflineDraft = (): Inspection => ({
    id: uuid(),
    productName,
    brand,
    category,
    barcode: null,
    images,
    declarations: [],
    ruleResults: [],
    status: "DRAFT",
    inspectorId: user!.id,
    inspectorName: user!.fullName,
    inspectorRole: user!.role,
    location: null,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    synced: false,
    notes: "",
    ruleVersion: "unsynced"
  });

  const applyAutoFill = (analyzed: Inspection) => {
    // Product Name/Brand are optional at the Details step — if left blank,
    // pre-fill them here from what OCR/extraction actually found
    // (COMMON_NAME declaration), so the inspector confirms/corrects a real
    // reading instead of hand-transcribing the label before ever scanning
    // it. Nothing is silently saved — this only sets the editable fields
    // shown in Human Verification below; submitVerificationAndFinalize is
    // what actually persists whatever the inspector confirms.
    const commonName = analyzed.declarations.find((d) => d.declarationType === "COMMON_NAME");
    setVerifiedProductName(analyzed.productName?.trim() || commonName?.detectedText || "");
    setVerifiedBrand(analyzed.brand?.trim() || "");
  };

  const runInspection = async () => {
    setBusy(true);
    setError(null);
    setStep("PROCESSING");
    try {
      // 1. Create the inspection record server-side.
      const created = await createInspection({ productName, brand, category });

      // 2. Upload every captured angle — each triggers the backend's
      //    OpenCV preprocessing pipeline on arrival (see cv_service.py).
      for (const image of images) {
        await uploadInspectionImage(created.id, image);
      }

      // 3. Kick off YOLO region detection -> PaddleOCR -> declaration
      //    extraction -> font/readability analysis -> barcode cross-check
      //    -> rule engine evaluation, all server-side.
      const analyzed = await runAnalysis(created.id);
      setInspection(analyzed);
      applyAutoFill(analyzed);
      setStep("RESULT");
    } catch (err) {
      if (isBackendUnreachable(err)) {
        // Real offline-first path: persist the draft locally with everything
        // captured so far. It will be uploaded and analyzed for real once
        // connectivity returns (see services/syncService.ts) — nothing here
        // fabricates OCR or compliance results while offline.
        const draft = buildOfflineDraft();
        await saveInspectionLocally(draft);
        setInspection(draft);
        setStep("SAVED");
      } else {
        setError("Analysis failed. You can retry, or save the captured images and retry later.");
        setStep("CAPTURE");
      }
    } finally {
      setBusy(false);
    }
  };

  const runEcommerceInspection = async () => {
    if (!listingUrl.trim()) return;
    setBusy(true);
    setError(null);
    setStep("PROCESSING");
    try {
      // 1. Create the inspection record server-side (same record type as a
      //    physical inspection — only source_type differs).
      const created = await createInspection({ productName, brand, category });

      // 2. Server-side pipeline: fetch listing -> HTML/JSON-LD/visible-text
      //    extraction -> product image download -> existing PaddleOCR
      //    pipeline on those images -> multimodal AI extraction for any
      //    field still missing -> the SAME unmodified rule engine used for
      //    physical inspections. The AI step never decides compliance —
      //    see backend/app/services/multimodal_service.py.
      const analyzed = await analyzeEcommerceListing(created.id, listingUrl.trim());
      setInspection(analyzed);
      applyAutoFill(analyzed);
      setStep("RESULT");
    } catch (err) {
      // Fetching an external listing needs real connectivity — there's no
      // meaningful offline fallback for this mode (unlike photo capture),
      // so this is a plain retryable error rather than an offline-queue save.
      if (isBackendUnreachable(err)) {
        setError("Could not reach the backend to analyze this listing. Check your connection and try again.");
      } else {
        const message = err instanceof Error ? err.message : "Could not analyze this listing.";
        setError(message || "Could not analyze this listing. Check the URL and try again.");
      }
      setStep("ECOMMERCE_INPUT");
    } finally {
      setBusy(false);
    }
  };

  const submitVerificationAndFinalize = async () => {
    if (!inspection) return;
    setBusy(true);
    try {
      await submitHumanVerification(inspection.id, { notes, productName: verifiedProductName, brand: verifiedBrand });
      const finalized = await finalizeInspection(inspection.id);
      setInspection(finalized);
      navigate(`/inspections/${finalized.id}`);
    } catch (err) {
      setError("Could not finalize inspection. It remains saved as a draft for review.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <TopBar title="New Inspection" />
      <div className="app-content">
        {step === "DETAILS" && (
          <div className="panel">
            <div className="panel-title">Inspection Mode</div>
            <div className="mode-selector">
              {MODES.map((m) => (
                <button
                  key={m.id}
                  type="button"
                  className={`mode-option ${mode === m.id ? "active" : ""}`}
                  onClick={() => setMode(m.id)}
                >
                  <span className="mode-icon">{m.icon}</span>
                  <span className="mode-label">{m.label}</span>
                  <span className="mode-blurb">{m.blurb}</span>
                </button>
              ))}
            </div>

            <div className="panel-title" style={{ marginTop: 20 }}>{t("inspection.details.title")}</div>
            <div className="field">
              <label>{t("inspection.details.productName")} <span style={{ color: "var(--color-steel)", fontWeight: 400 }}>(optional — will be filled in from OCR if left blank)</span></label>
              <input value={productName} onChange={(e) => setProductName(e.target.value)} />
            </div>
            <div className="field">
              <label>{t("inspection.details.brand")} <span style={{ color: "var(--color-steel)", fontWeight: 400 }}>(optional)</span></label>
              <input value={brand} onChange={(e) => setBrand(e.target.value)} />
            </div>
            <div className="field">
              <label>{t("inspection.details.category")}</label>
              <select value={category} onChange={(e) => setCategory(e.target.value)}>
                <option>Packaged Food</option>
                <option>Cosmetics</option>
                <option>Household Chemicals</option>
                <option>Stationery</option>
                <option>Electronics</option>
                <option>Electronics Accessory</option>
                <option>Other</option>
              </select>
            </div>
            {isElectronic && mode !== "ECOMMERCE" && (
              <p style={{ fontSize: 12.5, color: "var(--color-steel)" }}>
                This category requires a barcode/QR capture — it will be scanned and cross-checked
                against the product registry.
              </p>
            )}
            <button
              className="btn"
              onClick={() => setStep(mode === "ECOMMERCE" ? "ECOMMERCE_INPUT" : "CAPTURE")}
            >
              {mode === "ECOMMERCE" ? t("inspection.details.continueListing") : t("inspection.details.continueCamera")}
            </button>
          </div>
        )}

        {step === "CAPTURE" && (
          <div className="panel">
            <div className="panel-title">{mode === "LABEL" ? t("inspection.capture.title.label") : t("inspection.capture.title.package")}</div>

            <div style={{ marginBottom: 16 }}>
              <button
                className="btn secondary"
                type="button"
                onClick={() => {
                  setImages((prev) => prev.filter((i) => i.slot === "barcode"));
                  setUseSpinScan((v) => !v);
                }}
              >
                {useSpinScan ? t("inspection.capture.spinToggleOff") : t("inspection.capture.spinToggleOn")}
              </button>
              {!useSpinScan && (
                <p style={{ fontSize: 12, color: "var(--color-steel)", marginTop: 6 }}>
                  {t("inspection.capture.spinHint")}
                </p>
              )}
            </div>

            {useSpinScan ? (
              <>
                <SpinCapture
                  slotPrefix={spinPrefix}
                  onComplete={(spinFrames) =>
                    setImages((prev) => [...prev.filter((i) => !i.slot.startsWith(spinPrefix)), ...spinFrames])
                  }
                  onCancel={() => setUseSpinScan(false)}
                />
                {images.some((i) => i.slot.startsWith(spinPrefix)) && (
                  <p style={{ fontSize: 12.5, color: "var(--color-verdict-green)", marginTop: 8 }}>
                    ✓ {images.filter((i) => i.slot.startsWith(spinPrefix)).length} spin-scan frame(s) captured.
                  </p>
                )}
                {isElectronic && (
                  <div style={{ marginTop: 20 }}>
                    <div className="panel-title" style={{ fontSize: 14 }}>Barcode / QR</div>
                    {images.some((i) => i.slot === "barcode") ? (
                      <p style={{ fontSize: 12.5, color: "var(--color-verdict-green)" }}>✓ Barcode/QR captured.</p>
                    ) : (
                      <CameraCapture
                        guidanceLabel="Fill the frame with the barcode or QR code. Hold steady for a sharp capture."
                        onCapture={(dataUrl, quality) =>
                          setImages((prev) => [
                            ...prev,
                            {
                              slot: "barcode",
                              dataUrl,
                              capturedAt: new Date().toISOString(),
                              qualityFlags: quality.flags,
                              uploaded: false
                            }
                          ])
                        }
                      />
                    )}
                  </div>
                )}
              </>
            ) : (
              <MultiAngleCapture
                images={images}
                onImagesChange={setImages}
                requireBarcode={isElectronic}
                mode={mode === "LABEL" ? "LABEL" : "PACKAGE"}
              />
            )}

            {error && <p style={{ color: "var(--color-violation-red)", marginTop: 12 }}>{error}</p>}
            <div style={{ marginTop: 20 }}>
              <button className="btn" disabled={!captureComplete || busy} onClick={runInspection}>
                {t("inspection.capture.runAnalysis")}
              </button>
            </div>
          </div>
        )}

        {step === "ECOMMERCE_INPUT" && (
          <div className="panel">
            <div className="panel-title">{t("inspection.ecommerce.title")}</div>
            <p style={{ fontSize: 13, color: "var(--color-steel)" }}>
              {t("inspection.ecommerce.explain")}
            </p>
            <div className="field">
              <label>{t("inspection.ecommerce.urlLabel")}</label>
              <input
                type="url"
                placeholder="https://example.com/product/..."
                value={listingUrl}
                onChange={(e) => setListingUrl(e.target.value)}
              />
            </div>
            {error && <p style={{ color: "var(--color-violation-red)" }}>{error}</p>}
            <button className="btn" disabled={!listingUrl.trim() || busy} onClick={runEcommerceInspection}>
              {t("inspection.ecommerce.analyzeButton")}
            </button>
          </div>
        )}

        {step === "PROCESSING" && (
          <div className="panel">
            <div className="panel-title">{t("inspection.processing.title")}</div>
            {mode === "ECOMMERCE" ? (
              <p>
                {t("inspection.processing.ecommerce")}
              </p>
            ) : (
              <p>{t("inspection.processing.photo")}</p>
            )}
          </div>
        )}

        {step === "SAVED" && inspection && (
          <div className="panel">
            <div className="panel-title">{t("inspection.saved.title")}</div>
            <p>
              The backend was unreachable, so this inspection (product details and {images.length} captured
              images) was saved locally on this device. It will run through OCR and compliance analysis
              automatically once connectivity returns — check the Offline Queue page for sync status.
            </p>
            <button className="btn" onClick={() => navigate("/offline-queue")}>{t("inspection.saved.goToQueue")}</button>
          </div>
        )}

        {step === "RESULT" && inspection && (
          <>
            <div className="panel" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div>
                <div className="panel-title" style={{ marginBottom: 4 }}>{t("inspection.result.title")}</div>
                <p style={{ fontSize: 13, color: "var(--color-steel)", margin: 0 }}>
                  {inspection.productName} — {inspection.brand}
                </p>
              </div>
              <ComplianceStamp status={inspection.status} />
            </div>

            {inspection.sourceType === "ECOMMERCE_LISTING" && (
              <div className="panel">
                <div className="panel-title">{t("inspection.result.listingSource")}</div>
                <p style={{ fontSize: 13 }}>
                  <a href={inspection.sourceUrl ?? "#"} target="_blank" rel="noreferrer" className="mono">
                    {inspection.sourceUrl}
                  </a>
                </p>
                {inspection.ecommerceRawData && (
                  <>
                    <p style={{ fontSize: 13, color: "var(--color-steel)" }}>
                      <strong>{inspection.ecommerceRawData.title}</strong>
                      {inspection.ecommerceRawData.price &&
                        ` · ${inspection.ecommerceRawData.currency ?? ""} ${inspection.ecommerceRawData.price}`}
                    </p>
                    {inspection.ecommerceRawData.aiExtractionUsed && (
                      <p style={{ fontSize: 12.5, color: "var(--color-review-amber)" }}>
                        Some declarations below were filled in by AI extraction from unstructured
                        content and are marked "AI Extracted — Needs Verification". These are always
                        REVIEW findings, never an automatic PASS.
                      </p>
                    )}
                  </>
                )}
              </div>
            )}

            <div className="panel">
              <div className="panel-title">{t("inspection.result.declarations")}</div>
              <DeclarationTable declarations={inspection.declarations} />
            </div>

            <div className="panel">
              <div className="panel-title">{t("inspection.result.barcode")}</div>
              {!isElectronic ? (
                <p style={{ fontSize: 13, color: "var(--color-steel)" }}>
                  {t("inspection.result.barcode.notApplicable")}
                </p>
              ) : inspection.barcode ? (
                <p>
                  <span className="mono">{inspection.barcode.rawValue ?? "Not decoded"}</span>
                  {" · "}
                  {inspection.barcode.registryMatch === "MATCH" && "✓ Matches product registry"}
                  {inspection.barcode.registryMatch === "MISMATCH" && "⚠ Product information mismatch — " + inspection.barcode.note}
                  {inspection.barcode.registryMatch === "NOT_FOUND" && "⚠ Barcode not found in registry — " + inspection.barcode.note}
                  {inspection.barcode.registryMatch === "NOT_SCANNED" && ("Barcode not scanned — " + inspection.barcode.note)}
                  {inspection.barcode.registryMatch === "NOT_APPLICABLE" && "Not applicable to this category"}
                </p>
              ) : (
                <p>No barcode result.</p>
              )}
            </div>

            <div className="panel">
              <div className="panel-title">{t("inspection.result.ruleCompliance")}</div>
              <RuleResultList results={inspection.ruleResults} />
            </div>

            <div className="panel">
              <div className="panel-title">{t("inspection.result.humanVerification")}</div>
              <p style={{ fontSize: 13, color: "var(--color-steel)" }}>
                {t("inspection.result.humanVerification.blurb")}
              </p>
              <div className="field">
                <label>{t("inspection.details.productName")}</label>
                <input value={verifiedProductName} onChange={(e) => setVerifiedProductName(e.target.value)} />
              </div>
              <div className="field">
                <label>{t("inspection.details.brand")}</label>
                <input value={verifiedBrand} onChange={(e) => setVerifiedBrand(e.target.value)} />
              </div>
              <div className="field">
                <label>{t("inspection.result.notes")}</label>
                <input value={notes} onChange={(e) => setNotes(e.target.value)} />
              </div>
              {error && <p style={{ color: "var(--color-violation-red)" }}>{error}</p>}
              <button className="btn" disabled={busy} onClick={submitVerificationAndFinalize}>
                {t("inspection.result.confirmSave")}
              </button>
            </div>
          </>
        )}
      </div>
    </>
  );
}
