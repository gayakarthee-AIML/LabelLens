// Shared domain types. These mirror the Pydantic schemas in
// backend/app/schemas/*.py — keep the two in sync when either side changes.

export type UserRole =
  | "INSPECTOR"
  | "SENIOR_INSPECTOR"
  | "ADMINISTRATOR"
  | "REGULATOR";

export interface RoleDescriptor {
  id: UserRole;
  label: string;
  tagline: string;
  description: string;
}

export interface AuthUser {
  id: string;
  fullName: string;
  officialId: string;
  role: UserRole;
  jurisdiction?: string;
}

export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
  tokenType: "bearer";
  expiresIn: number;
}

export interface LoginPayload {
  role: UserRole; // UX hint only — server re-derives the real role from the account
  officialId: string;
  password: string;
}

export type DeclarationType =
  | "COMMON_NAME"
  | "NET_QUANTITY"
  | "MRP"
  | "MANUFACTURER_DETAILS"
  | "COUNTRY_OF_ORIGIN"
  | "MFG_DATE"
  | "CONSUMER_CARE"
  | "UNIT_SALE_PRICE";

export type DeclarationStatus = "PRESENT" | "MISSING" | "AMBIGUOUS" | "REVIEW";

export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface Declaration {
  declarationType: DeclarationType;
  detectedText: string | null;
  confidence: number; // 0..1
  boundingBox: BoundingBox | null;
  sourceImage: string; // image slot id (e.g. "front"), or "webpage" / "ai_extraction" for e-commerce listings
  status: DeclarationStatus;
  applicableRule: string; // rule id
  estimatedTextHeightPx: number | null;
  readability: "GOOD" | "POOR" | "REVIEW" | null;
  /** Only set when sourceImage === "ai_extraction" — the model's own short explanation of where it saw this value. Never used by the rule engine, display-only. */
  aiRationale?: string;
}

export type RuleValidationType =
  | "PRESENCE"
  | "FORMAT"
  | "TEXT_PATTERN"
  | "NUMERIC"
  | "RANGE"
  | "FONT_SIZE"
  | "READABILITY"
  | "CROSS_FIELD"
  | "BARCODE_MATCH";

export type RuleSeverity = "CRITICAL" | "MAJOR" | "MINOR" | "ADVISORY";

export interface ComplianceRule {
  ruleId: string;
  name: string;
  description: string;
  applicableCategory: string;
  requirement: string;
  validationType: RuleValidationType;
  severity: RuleSeverity;
  source: string;
  version: string;
  effectiveDate: string;
  enabled: boolean;
}

export type RuleFindingStatus = "PASS" | "FAIL" | "REVIEW";

export interface RuleResult {
  rule: ComplianceRule;
  status: RuleFindingStatus;
  finding: string;
  evidence: string;
  confidence: number;
  recommendation: string;
}

export type BarcodeSymbology = "EAN13" | "EAN8" | "UPC_A" | "UPC_E" | "QR" | "UNKNOWN";

export interface BarcodeResult {
  rawValue: string | null;
  symbology: BarcodeSymbology | null;
  registryMatch: "MATCH" | "MISMATCH" | "NOT_FOUND" | "NOT_SCANNED" | "NOT_APPLICABLE";
  matchedProduct?: {
    name: string;
    brand: string;
    manufacturer: string;
    declaredNetQuantity: string;
  };
  note: string; // always phrased as risk/verification language, never "proven counterfeit"
}

// The backend's InspectionImage.slot is a free string (no enum) — these are
// the fixed slot names the static capture UI uses, plus a catch-all for
// dynamically-named slots (spin-capture frames, e-commerce listing images).
export type ImageSlot =
  | "front"
  | "back"
  | "left"
  | "right"
  | "barcode"
  | "top"
  | "bottom"
  | "additional"
  | (string & {});

export interface CapturedImage {
  slot: ImageSlot;
  dataUrl: string;
  capturedAt: string;
  qualityFlags: string[]; // e.g. ["LOW_BRIGHTNESS", "BLUR_DETECTED"]
  uploaded: boolean;
  remoteImageId?: string;
  note?: string;
}

export type InspectionStatus = "COMPLIANT" | "NON_COMPLIANT" | "REVIEW_REQUIRED" | "DRAFT";

export type InspectionSourceType = "PHYSICAL_INSPECTION" | "ECOMMERCE_LISTING";

export interface EcommerceRawData {
  title: string;
  description: string;
  price: string | null;
  currency: string | null;
  brandFromListing: string | null;
  gtin: string | null;
  imageUrls: string[];
  jsonLdProductsFound: number;
  aiExtractionUsed: boolean;
}

export interface Inspection {
  id: string;
  productName: string;
  brand: string;
  category: string;
  barcode: BarcodeResult | null;
  images: CapturedImage[];
  declarations: Declaration[];
  ruleResults: RuleResult[];
  status: InspectionStatus;
  inspectorId: string;
  inspectorName: string;
  inspectorRole: UserRole;
  location: string | null;
  createdAt: string;
  updatedAt: string;
  synced: boolean;
  notes: string;
  ruleVersion: string;
  isElectronicCategory?: boolean;
  sourceType?: InspectionSourceType;
  sourceUrl?: string | null;
  ecommerceRawData?: EcommerceRawData | null;
}

export interface DashboardSummary {
  totalInspections: number;
  todayInspections: number;
  compliant: number;
  nonCompliant: number;
  reviewRequired: number;
  violationsDetected: number;
  pendingReviews: number;
  pendingSync: number;
  complianceTrend: { date: string; compliant: number; nonCompliant: number; review: number }[];
  violationsByCategory: { category: string; count: number }[];
  commonViolations: { rule: string; count: number }[];
}

export interface SyncQueueEntry {
  inspectionId: string;
  attempts: number;
  lastAttemptAt: string | null;
  lastError: string | null;
  status: "PENDING" | "SYNCING" | "SYNCED" | "FAILED";
}

export interface EvidenceImage {
  remoteImageId: string;
  slot: ImageSlot;
  originalUrl: string;
  processedUrl: string | null;
  capturedAt: string;
  quality: { brightness: number | null; blurScore: number | null; glarePct: number | null; flags: string[] };
  ocrWords: { text: string; confidence: number; box: number[][]; lang: string }[];
  note: string;
  relatedDeclarations: Record<string, unknown>[];
}

export interface EvidenceBundle {
  inspectionId: string;
  images: EvidenceImage[];
  ruleResults: RuleResult[];
}

export interface UserRecord {
  id: string;
  officialId: string;
  fullName: string;
  role: UserRole;
  jurisdiction: string | null;
  isActive: boolean;
}

export interface ReportHistoryEntry {
  inspectionId: string;
  productName: string;
  format: "pdf" | "docx";
  generatedBy: UserRole;
  generatedAt: string;
}

// --- Font size checking (reference-card calibration) ---
// Deliberately separate from the OCR/declaration pipeline above — see
// backend/app/services/font_size_service.py.

export interface CardDetection {
  found: boolean;
  pxPerMm: number | null;
  confidence: number;
  message: string;
}

export interface FontMeasurement {
  text: string;
  confidence: number;
  heightPx: number;
  heightMm: number;
  requiredMm: number | null;
  standardName: string | null;
  status: "PASS" | "FAIL" | "REVIEW";
  note: string;
}

export type FontSizeOverallStatus = "PASS" | "FAIL" | "REVIEW" | "NEEDS_CARD";

export interface FontSizeCheckResult {
  card: CardDetection;
  measurements: FontMeasurement[];
  overallStatus: FontSizeOverallStatus;
}

export interface FontSizeStandard {
  standardId: string;
  name: string;
  keyword: string;
  minHeightMm: number;
  source: string;
  version: string;
  enabled: boolean;
}

export interface AnalyticsSummary {
  totalInspections: number;
  manualReviewRate: number;
  barcodeMismatchRate: number;
  averageOcrConfidence: number;
  commonViolations: { rule: string; count: number }[];
  inspectionsByCategory: { category: string; count: number }[];
}
