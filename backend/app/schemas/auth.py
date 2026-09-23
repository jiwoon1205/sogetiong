from pydantic import BaseModel, EmailStr


class VerificationRequest(BaseModel):
    school_id: int
    email: EmailStr


class VerifyCodeRequest(BaseModel):
    email: EmailStr
    code: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    nickname: str
    campus_id: str
    gender: str
    age: int


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
