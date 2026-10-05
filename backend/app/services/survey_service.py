"""사용자 설문 (2026-10-05).

규칙
- 관리자가 "설문 받기"를 켜면, 아직 답하지 않은 사용자는 로그인·가입 직후 설문 화면만 보게 된다 (꼭 답해야 넘어감).
- 계정 하나당 한 번만 답할 수 있다. 답한 사람에게는 다시 뜨지 않는다.
- 관리자가 끄면 바로 아무에게도 뜨지 않는다. 응답은 그대로 남는다.
- 질문 내용이 바뀌면 SURVEY_KEY를 바꾼다 → 새 설문으로 취급되어 모두에게 다시 뜬다.
"""

import uuid

from sqlalchemy.orm import Session

from app.models.survey import AppSetting, SurveyResponse

SURVEY_KEY = "2026-10-launch"
OPEN_SETTING = "survey_open"

# 1번 질문: 정식 배포 후 외모 평가 방식
APPEARANCE_CHOICES: dict[str, str] = {
    "AI_ONLY": "지금처럼 AI 평가 (4가지 기준)",
    "AI_NEW_CRITERIA": "AI 평가 + 기준 변경",
    "AI_PLUS_ADMIN": "AI 점수 + 운영자 ±2점 조정",
    "ADMIN_ONLY": "운영자 혼자 평가",
    "OTHER": "기타",
}

# 유료 시스템 만족도 (5단계)
PAYMENT_RATINGS: dict[int, str] = {
    5: "매우 만족",
    4: "만족",
    3: "보통",
    2: "불만족",
    1: "매우 불만족",
}


def is_open(db: Session) -> bool:
    row = db.get(AppSetting, OPEN_SETTING)
    return row is not None and row.value == "true"


def set_open(db: Session, open_: bool) -> None:
    """commit은 부르는 쪽에서."""
    row = db.get(AppSetting, OPEN_SETTING)
    value = "true" if open_ else "false"
    if row is None:
        db.add(AppSetting(key=OPEN_SETTING, value=value))
    else:
        row.value = value


def has_answered(db: Session, user_id: uuid.UUID) -> bool:
    return (
        db.query(SurveyResponse.id)
        .filter(SurveyResponse.user_id == user_id, SurveyResponse.survey_key == SURVEY_KEY)
        .first()
        is not None
    )


def pending(db: Session, user_id: uuid.UUID) -> bool:
    """이 사람에게 지금 설문을 띄워야 하는지."""
    return is_open(db) and not has_answered(db, user_id)
