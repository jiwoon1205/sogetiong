import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.config import get_settings


def check_password_policy(value: str) -> str:
    """가입과 비밀번호 재설정이 같은 규칙을 쓴다."""
    min_len = get_settings().password_min_length
    if len(value) < min_len:
        raise ValueError(f"비밀번호는 {min_len}자 이상이어야 합니다.")
    if value.isdigit() or value.isalpha():
        raise ValueError("비밀번호는 영문과 숫자/기호를 섞어야 합니다.")
    return value


class SendCodeRequest(BaseModel):
    email: EmailStr


class VerifyCodeRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class VerifyCodeResponse(BaseModel):
    verification_ticket: str
    expires_in_minutes: int


class RegisterRequest(BaseModel):
    verification_ticket: str = Field(min_length=10, max_length=200)
    password: str = Field(max_length=128)
    nickname: str = Field(min_length=2, max_length=20)
    gender: Literal["MALE", "FEMALE"]
    birth_date: date
    campus_id: uuid.UUID
    # 선택 입력 (Layer 3, 관리자만 접근)
    real_name: str | None = Field(default=None, max_length=60)
    student_id: str | None = Field(default=None, max_length=30)
    agree_terms: bool
    agree_privacy: bool
    agree_appearance_public: bool  # 외적 평가 점수 공개 동의

    @field_validator("password")
    @classmethod
    def password_policy(cls, value: str) -> str:
        return check_password_policy(value)

    @field_validator("nickname")
    @classmethod
    def strip_nickname(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("닉네임은 2자 이상이어야 합니다.")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class PasswordResetRequest(BaseModel):
    """1단계: 재설정 코드 요청"""

    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """2단계: 코드 + 새 비밀번호"""

    email: EmailStr
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    new_password: str = Field(max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_policy(cls, value: str) -> str:
        return check_password_policy(value)


class DeleteAccountRequest(BaseModel):
    password: str = Field(max_length=128)
