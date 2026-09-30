import uuid
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, model_validator

Score = Field(default=None, ge=1, le=10)


class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class AdminTwoFactorRequest(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


class EvaluationRequest(BaseModel):
    """PUT /admin/photo-reviews/{photo_id}/evaluation"""

    decision: Literal["APPROVED", "REJECTED"]
    overall_impression: int | None = Score  # 전체적인 인상
    style: int | None = Score  # 스타일
    grooming: int | None = Score  # 자기관리
    photo_vibe: int | None = Score  # 사진 분위기
    # 외모 등급 (상/중/하). 승인할 때 필수. 내부 전용이라 사용자에게는 절대 보이지 않는다.
    tier: Literal["HIGH", "MID", "LOW"] | None = None
    note: str | None = Field(default=None, max_length=500)  # 관리자 전용
    reject_reason: str | None = Field(default=None, max_length=300)  # 사용자에게 전달

    @model_validator(mode="after")
    def check(self):
        scores = (self.overall_impression, self.style, self.grooming, self.photo_vibe)
        if self.decision == "APPROVED" and any(s is None for s in scores):
            raise ValueError("승인하려면 4개 항목 점수가 모두 필요합니다.")
        if self.decision == "APPROVED" and self.tier is None:
            raise ValueError("승인하려면 외모 등급(상/중/하)을 골라주세요.")
        if self.decision == "REJECTED" and not self.reject_reason:
            raise ValueError("반려 사유를 입력해주세요.")
        return self


class UserDepartmentRequest(BaseModel):
    """PATCH /admin/users/{user_id}/department — 사용자의 학과 변경 요청 처리"""

    department_id: uuid.UUID
    reason: str = Field(min_length=2, max_length=300)  # 예: "가입 메일로 요청, 컴퓨터공학부 → 통계학과"


class UserGenderRequest(BaseModel):
    """PATCH /admin/users/{user_id}/gender — 성별·원하는 성별 변경 요청 처리 (사용자는 직접 못 바꾼다)

    바꿀 항목만 보낸다. 둘 다 비우면 400.
    """

    gender: Literal["MALE", "FEMALE"] | None = None
    preferred_gender: Literal["MALE", "FEMALE", "ANY"] | None = None
    reason: str = Field(min_length=2, max_length=300)  # 예: "가입 메일로 요청, 원하는 성별 여성 → 상관없음"

    @model_validator(mode="after")
    def needs_change(self):
        if self.gender is None and self.preferred_gender is None:
            raise ValueError("바꿀 항목을 골라주세요.")
        return self


class AppearanceTierRequest(BaseModel):
    """PATCH /admin/users/{user_id}/appearance-tier — 외모 등급만 다시 정하기 (점수는 그대로)"""

    tier: Literal["HIGH", "MID", "LOW"]
    reason: str = Field(min_length=2, max_length=300)


class UserStatusRequest(BaseModel):
    # DELETED: 탈퇴 후 정지된 계정의 정지를 풀 때만 쓴다 (다시 '탈퇴' 상태로)
    status: Literal["ACTIVE", "SUSPENDED", "BANNED", "DELETED"]
    reason: str = Field(min_length=2, max_length=300)


class ReportUpdateRequest(BaseModel):
    status: Literal["IN_REVIEW", "RESOLVED", "DISMISSED"]
    admin_note: str | None = Field(default=None, max_length=1000)
