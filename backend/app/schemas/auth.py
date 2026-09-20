from pydantic import BaseModel


class LoginRequest(BaseModel):
    role: str  # UX hint only, see app/api/routers/auth.py for why this is not trusted
    officialId: str
    password: str


class RefreshRequest(BaseModel):
    refreshToken: str


class AuthUserOut(BaseModel):
    id: str
    fullName: str
    officialId: str
    role: str
    jurisdiction: str | None = None

    class Config:
        from_attributes = True


class TokenPair(BaseModel):
    accessToken: str
    refreshToken: str
    tokenType: str = "bearer"
    expiresIn: int


class LoginResponse(BaseModel):
    user: AuthUserOut
    tokens: TokenPair
