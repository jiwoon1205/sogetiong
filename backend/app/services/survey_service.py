"""사용자 설문 (2026-10-05 → 2026-11-14 → 2026-11-22 찬반 투표로 교체).

규칙
- 설문이 켜져 있으면, 아직 답하지 않은 사용자는 로그인·가입 직후 설문 화면을 먼저 보게 된다.
- 계정 하나당 한 번만 답할 수 있다. 답한 사람에게는 다시 뜨지 않는다.
- 관리자가 끄면 바로 아무에게도 뜨지 않는다. 응답은 그대로 남는다.
- 질문 내용이 바뀌면 SURVEY_KEY를 바꾼다 → 새 설문으로 취급되어 모두에게 다시 뜬다.

2026-11-22 (지금 설문): 개선사항 찬반 투표 "2026-11-friend-goal"
  많은 분이 찾는 관계에서 '대학교 친구'를 없애 달라고 요청함 → 없애는 데 찬성 / 반대.
  - 찬성(AGREE) 또는 반대(DISAGREE)를 꼭 골라야 제출된다. 하고 싶은 말은 선택.
  - **모든 사용자에게 뜨도록 처음부터 켜져 있다** (관리자 화면에서 끌 수 있음).
    켜짐/꺼짐은 설문마다 따로 저장한다 ("survey_open:<설문 이름>", 값이 없으면 켜짐).
  - 지난 설문(2026-11-feedback)에 답했어도 이 설문은 한 번 더 뜬다.
옛 응답은 DB에 그대로 남아 있다 (관리자 화면에는 지금 설문만 보임).
"""

import uuid

from sqlalchemy.orm import Session

from app.models.survey import AppSetting, SurveyResponse

SURVEY_KEY = "2026-11-friend-goal"
OPEN_SETTING = f"survey_open:{SURVEY_KEY}"
VOTES = ("AGREE", "DISAGREE")


def is_open(db: Session) -> bool:
    """값이 없으면 켜진 것 (모든 사용자에게 뜨게, 2026-11-22)."""
    row = db.get(AppSetting, OPEN_SETTING)
    return row is None or row.value == "true"


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
