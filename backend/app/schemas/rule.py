from pydantic import BaseModel


class RuleOut(BaseModel):
    ruleId: str
    name: str
    description: str
    applicableCategory: str
    requirement: str
    validationType: str
    severity: str
    source: str
    version: str
    effectiveDate: str
    enabled: bool

    class Config:
        from_attributes = True


class RuleCreate(BaseModel):
    ruleId: str
    name: str
    description: str
    applicableCategory: str
    requirement: str
    validationType: str
    severity: str
    source: str
    effectiveDate: str
    enabled: bool = True
    params: dict = {}


class RulePatch(BaseModel):
    name: str | None = None
    description: str | None = None
    requirement: str | None = None
    severity: str | None = None
    effectiveDate: str | None = None
    enabled: bool | None = None
    params: dict | None = None


class RuleToggle(BaseModel):
    enabled: bool


class RuleHistoryEntry(BaseModel):
    version: str
    publishedAt: str
    source: str
    changeSummary: str
