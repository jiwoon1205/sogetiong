"""하루 매칭 한도 (2026-10-06 변경).

규칙 (사용자와 확정)
- 한국 시간 0시부터 매칭이 N번(기본 3번, 설정 DAILY_MATCH_LIMIT) 생기면, 그날 남은 시간 동안
  그 사람의 **추천 탭에 "나를 이미 LIKE한 사람"이 나오지 않는다**.
  → 추천에서 LIKE를 눌러 바로 매칭되는 일이 없어진다.
- 한국 시간 밤 12시가 지나면 자동으로 풀린다. 다음 날 또 N번 매칭되면 또 걸린다.
- 본인은 절대 알 수 없다: 화면 문구·알림·API 응답 어디에도 표시하지 않는다.
  추천 카드가 몇 장 덜 나올 뿐이다.
- VIP "받은 LIKE" 목록은 기존과 똑같이 보이고, 거기서 LIKE하면 보통대로 매칭된다.
- 숨김 매칭(HIDDEN)을 만들지 않는다. 관리자가 거는 "매칭 정지"와는 별개다 (그건 그대로).
- 상대가 나를 추천에서 보고 LIKE해서 생기는 매칭은 막지 않는다.
- VIP 테스트 계정(운영자)은 제외한다.

이전 방식 (2026-10-06 오전): 3번째 매칭 직후 "매칭 정지"를 자동으로 켜고 관리자가 풀 때까지 유지 → 폐기.

세는 방법
- 오늘 생긴 매칭 중 숨김(HIDDEN)이 아닌 것. 나중에 대화를 끝냈거나 차단한 매칭도 "매칭된 것"이라 센다.
- 관리자가 "다시 보이게"로 공개한 매칭은 세지 않는다 (공개하면 매칭 시각이 지금으로 바뀌기 때문).
"""

import uuid
from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.time import kst_day_start
from app.models.admin import AuditLog
from app.models.matching import Like, Match
from app.models.user import User
from app.services import vip_service

# 이전 방식(자동 매칭 정지)의 감사 로그 이름. 이제 새로 쓰지 않지만, 관리자 화면이 옛 기록을 "자동"으로 표시할 때 쓴다.
AUTO_ACTION = "MATCH_AUTO_SUSPEND"


def matches_today(db: Session, user_id: uuid.UUID, now: datetime | None = None) -> int:
    """오늘(한국 시간 0시부터) 생긴 (숨김이 아닌) 매칭 수. 관리자가 공개한 숨김 매칭은 빼고 센다."""
    since = kst_day_start(now)
    ids = [
        str(mid)
        for (mid,) in db.query(Match.id)
        .filter(
            or_(Match.user_a_id == user_id, Match.user_b_id == user_id),
            Match.status != "HIDDEN",
            Match.created_at >= since,
        )
        .all()
    ]
    if not ids:
        return 0
    revealed = {
        tid
        for (tid,) in db.query(AuditLog.target_id)
        .filter(AuditLog.action == "MATCH_REVEAL", AuditLog.target_id.in_(ids))
        .all()
    }
    return len([i for i in ids if i not in revealed])


def reached_daily_limit(db: Session, user: User, now: datetime | None = None) -> bool:
    """오늘 매칭 한도에 닿았는지. True면 추천에서 "나를 LIKE한 사람"을 뺀다. 내부 전용 (응답에 넣지 말 것)."""
    limit = get_settings().daily_match_limit
    if limit <= 0 or vip_service.is_vip_tester(user):
        return False
    return matches_today(db, user.id, now) >= limit


def all_liker_ids(db: Session, user_id: uuid.UUID) -> set[uuid.UUID]:
    """나에게 LIKE를 보낸 모든 사람 (매칭 정지된 사람 포함). 추천에서 뺄 때 쓴다."""
    return {
        uid
        for (uid,) in db.query(Like.from_user_id).filter(Like.to_user_id == user_id, Like.action == "LIKE")
    }
