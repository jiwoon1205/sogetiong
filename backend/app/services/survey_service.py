"""사용자 설문 (2026-10-05, 2026-11-14 새 설문으로 교체).

규칙
- 관리자가 "설문 받기"를 켜면, 아직 답하지 않은 사용자는 로그인·가입 직후 설문 화면을 먼저 보게 된다.
- 계정 하나당 한 번만 답할 수 있다. 답한(또는 건너뛴) 사람에게는 다시 뜨지 않는다.
- 관리자가 끄면 바로 아무에게도 뜨지 않는다. 응답은 그대로 남는다.
- 질문 내용이 바뀌면 SURVEY_KEY를 바꾼다 → 새 설문으로 취급되어 모두에게 다시 뜬다.

2026-11-14: 옛 설문(정식 오픈 전, "2026-10-launch": 외모 평가 방식·유료 만족도)을 내리고
  새 설문("2026-11-feedback")으로 바꿈. 질문 2개, 둘 다 글로 답한다.
  1) 훕팅에서 개선했으면 하는 점  2) 새로 추가됐으면 하는 기능
  - 둘 중 하나 이상 적어야 제출할 수 있다.
  - 쓸 말이 없으면 "건너뛰기" → 빈 응답으로 저장되어 다시 안 뜬다 (억지로 쓰게 하지 않기 위해).
  옛 응답은 DB에 그대로 남아 있다 (관리자 화면에는 새 설문만 보임).
"""

import uuid

from sqlalchemy.orm import Session

from app.models.survey import AppSetting, SurveyResponse

SURVEY_KEY = "2026-11-feedback"
OPEN_SETTING = "survey_open"


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
