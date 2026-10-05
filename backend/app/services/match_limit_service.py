"""하루 매칭 횟수 제한 → 자동 매칭 정지 (2026-10-06).

규칙 (사용자와 확정)
- 한국 시간 0시부터 매칭이 N번(기본 3번, 설정 MATCH_AUTO_SUSPEND_DAILY) 생기면 그 사람을 매칭 정지한다.
  N번째 매칭은 보통대로 보이고, 그 다음 매칭부터 숨김(HIDDEN)이 된다.
- 기존 "매칭 정지"와 완전히 같은 상태다: 본인은 절대 모르고, 관리자가 풀 때까지 계속된다.
- 정지 중 생긴 숨김 매칭은 관리자가 하나씩 골라서 다시 보이게 한다.
- 추천 목록에는 그대로 나온다.

세는 방법
- 오늘 생긴 매칭 중 숨김(HIDDEN)이 아닌 것. 나중에 대화를 끝냈거나 차단한 매칭도 "매칭된 것"이라 센다.
- 관리자가 오늘 정지를 풀었다면 푼 뒤에 생긴 매칭만 센다 (풀자마자 다시 걸리지 않게).
- 관리자가 "다시 보이게"로 공개한 매칭은 세지 않는다 (공개하면 매칭 시각이 지금으로 바뀌기 때문).
- VIP 테스트 계정(운영자)은 제외한다.
"""

import uuid
from datetime import datetime

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.time import as_utc, kst_day_start, utcnow
from app.models.admin import AuditLog
from app.models.matching import Match
from app.models.user import User
from app.services import audit_service, vip_service

AUTO_ACTION = "MATCH_AUTO_SUSPEND"


def _count_since(db: Session, user_id: uuid.UUID, now: datetime | None = None) -> datetime:
    """언제부터 셀지: 오늘 0시(한국 시간)와 오늘 관리자가 정지를 푼 시각 중 늦은 쪽."""
    start = kst_day_start(now)
    last_unsuspend = (
        db.query(func.max(AuditLog.created_at))
        .filter(
            AuditLog.action == "MATCH_UNSUSPEND",
            AuditLog.target_id == str(user_id),
            AuditLog.created_at >= start,
        )
        .scalar()
    )
    return max(start, as_utc(last_unsuspend)) if last_unsuspend else start


def matches_today(db: Session, user_id: uuid.UUID, now: datetime | None = None) -> int:
    """오늘 생긴 (숨김이 아닌) 매칭 수. 관리자가 공개한 숨김 매칭은 빼고 센다."""
    since = _count_since(db, user_id, now)
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


def check_and_suspend(db: Session, user_ids: list[uuid.UUID], now: datetime | None = None) -> list[uuid.UUID]:
    """매칭이 새로 생긴 뒤 부른다. 오늘 매칭이 한도에 닿은 사람을 매칭 정지한다.
    정지된 사람의 ID 목록을 돌려준다. commit은 호출한 쪽에서 한다.
    사용자에게는 알림을 보내지 않는다 (정지 사실을 알 수 없게)."""
    limit = get_settings().match_auto_suspend_daily
    if limit <= 0:
        return []
    db.flush()  # 방금 만든 매칭도 세도록
    suspended: list[uuid.UUID] = []
    for uid in user_ids:
        user = db.get(User, uid)
        if user is None or user.match_suspended or vip_service.is_vip_tester(user):
            continue
        count = matches_today(db, uid, now)
        if count < limit:
            continue
        user.match_suspended = True
        user.match_suspended_at = now or utcnow()
        audit_service.record(
            db,
            admin_id=None,  # 관리자가 아니라 서버가 자동으로 함
            action=AUTO_ACTION,
            target_type="USER",
            target_id=user.id,
            metadata={"reason": f"하루 매칭 {limit}번 달성", "matches_today": count},
        )
        suspended.append(uid)
    return suspended
