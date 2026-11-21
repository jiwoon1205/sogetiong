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
    # 이 메일의 학교 (2026-10-24 경희대 확장): 가입 화면이 이 학교의 캠퍼스 목록을 보여준다
    university_id: str | None = None
    university_name: str | None = None
    # 여대 메일이면 "FEMALE" (가입할 때 성별을 고르지 않는다, 2026-11-21)
    fixed_gender: str | None = None


class RegisterRequest(BaseModel):
    verification_ticket: str = Field(min_length=10, max_length=200)
    password: str = Field(max_length=128)
    nickname: str = Field(min_length=2, max_length=20)
    gender: Literal["MALE", "FEMALE"]
    # 2026-11-07: '원하는 성별'은 없앴다 — 항상 이성 (서버가 성별의 반대로 정한다).
    # 예전 화면·앱이 보내도 받기만 하고 쓰지 않는다.
    preferred_gender: Literal["MALE", "FEMALE", "ANY"] | None = None
    birth_date: date
    campus_id: uuid.UUID
    # 선택 입력 (Layer 3, 관리자만 접근)
    real_name: str | None = Field(default=None, max_length=60)
    student_id: str | None = Field(default=None, max_length=30)
    agree_terms: bool
    agree_privacy: bool
    agree_appearance_public: bool  # 외적 평가 점수 공개 동의
    # 친구 초대 링크로 들어왔으면 그 코드 (2026-10-24). 틀린 코드·기간 밖이면 조용히 무시한다
    referral_code: str | None = Field(default=None, max_length=20)

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


# 탈퇴 사유 목록 (2026-11-16). 하나만 고른다. OTHER(기타)는 글을 꼭 적는다. 화면 순서도 이 순서
WITHDRAWAL_REASONS: dict[str, str] = {
    "DATING": "썸/연애 시작",
    "PRICE": "이용료 부담",
    "NO_MATCH": "매칭이 안 됨",
    "NO_ONE": "마음에 드는 사람이 없음",
    "CHAT": "대화가 잘 안 이어짐",
    "BAD_USER": "불쾌한 사용자를 만남",
    "BREAK": "잠깐 쉬고 싶음 / 다시 올게요",
    "OTHER": "기타",
}


class DeleteAccountRequest(BaseModel):
    password: str = Field(max_length=128)
    # 탈퇴 사유 (2026-11-16 필수, 목록에서 하나). 관리자만 본다
    reason_code: Literal["DATING", "PRICE", "NO_MATCH", "NO_ONE", "CHAT", "BAD_USER", "BREAK", "OTHER"] | None = None
    # 기타(OTHER)일 때 적는 글. 빈 칸·아이디(메일)만 적은 것은 delete_me에서 막는다.
    # reason_code 없이 글만 오면(예전 화면) 기타로 본다
    reason: str | None = Field(default=None, max_length=500)
