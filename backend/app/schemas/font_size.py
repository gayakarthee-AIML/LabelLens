from pydantic import BaseModel


class FontSizeStandardOut(BaseModel):
    standardId: str
    name: str
    keyword: str
    minHeightMm: float
    source: str
    version: str
    enabled: bool

    class Config:
        from_attributes = True


class FontSizeStandardPatch(BaseModel):
    name: str | None = None
    keyword: str | None = None
    minHeightMm: float | None = None
    source: str | None = None
    enabled: bool | None = None


class FontSizeStandardCreate(BaseModel):
    standardId: str
    name: str
    keyword: str = ""
    minHeightMm: float
    source: str = "Manually added by Administrator"
    enabled: bool = True


class CardDetectionOut(BaseModel):
    found: bool
    pxPerMm: float | None
    confidence: float
    message: str


class FontMeasurementOut(BaseModel):
    text: str
    confidence: float
    heightPx: float
    heightMm: float
    requiredMm: float | None
    standardName: str | None
    status: str
    note: str


class FontSizeCheckResult(BaseModel):
    card: CardDetectionOut
    measurements: list[FontMeasurementOut]
    overallStatus: str
