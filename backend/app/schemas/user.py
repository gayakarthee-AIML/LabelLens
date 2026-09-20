from pydantic import BaseModel


class UserOut(BaseModel):
    id: str
    officialId: str
    fullName: str
    role: str
    jurisdiction: str | None = None
    isActive: bool

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    officialId: str
    fullName: str
    role: str
    password: str
    jurisdiction: str | None = None


class UserUpdate(BaseModel):
    fullName: str | None = None
    role: str | None = None
    jurisdiction: str | None = None
    isActive: bool | None = None
    password: str | None = None  # admin-initiated reset; not the user's own change-password flow
