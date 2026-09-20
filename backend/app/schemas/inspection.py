from pydantic import BaseModel


class InspectionCreate(BaseModel):
    productName: str
    brand: str
    category: str
    location: str | None = None


class EcommerceAnalyzeRequest(BaseModel):
    url: str


class BoundingBoxOut(BaseModel):
    x: float
    y: float
    width: float
    height: float


class DeclarationOut(BaseModel):
    declarationType: str
    detectedText: str | None
    confidence: float
    boundingBox: BoundingBoxOut | None
    sourceImage: str
    status: str
    applicableRule: str
    estimatedTextHeightPx: float | None
    readability: str | None


class RuleResultOut(BaseModel):
    rule: dict
    status: str
    finding: str
    evidence: str
    confidence: float
    recommendation: str


class BarcodeResultOut(BaseModel):
    rawValue: str | None
    symbology: str | None
    registryMatch: str
    matchedProduct: dict | None = None
    note: str


class CapturedImageOut(BaseModel):
    slot: str
    dataUrl: str
    capturedAt: str
    qualityFlags: list[str]
    uploaded: bool
    remoteImageId: str | None = None


class InspectionOut(BaseModel):
    id: str
    productName: str
    brand: str
    category: str
    barcode: BarcodeResultOut | None
    images: list[CapturedImageOut]
    declarations: list[DeclarationOut]
    ruleResults: list[RuleResultOut]
    status: str
    inspectorId: str
    inspectorName: str
    inspectorRole: str
    location: str | None
    createdAt: str
    updatedAt: str
    synced: bool
    notes: str
    ruleVersion: str


class HumanVerificationRequest(BaseModel):
    declarationOverrides: list[dict] | None = None
    ruleOverrides: list[dict] | None = None
    notes: str | None = None
    # Product name/brand are optional at inspection creation (see the
    # brief's concern that requiring an inspector to type the product name
    # before scanning partly defeats the point of OCR) — the frontend
    # auto-fills these from the extracted COMMON_NAME/MANUFACTURER_DETAILS
    # declarations after analysis and lets the inspector confirm/correct
    # them here, which is what actually persists the final value.
    productName: str | None = None
    brand: str | None = None


class ImageUploadResponse(BaseModel):
    remoteImageId: str
    qualityFlags: list[str]
