"""감시 대상 기록 (2026-11-17). 관리자 전용 — 사용자에게는 절대 보이지 않는다.

캐주얼한 만남을 고르지 않은 사람(진지한 연애·대학교 친구·안 고름)이 지금 '캐주얼한 만남'을 고른 사람에게
좋아요·슈퍼 라이크를 보내거나, 보내려다 '찾는 관계가 달라요'로 막히면 기록한다.
사용자 응답·화면은 하나도 바뀌지 않는다 (기록만 조용히 남긴다).
"""

import uuid
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.time import utcnow
from app.models.watch import WatchEvent, WatchTarget
from app.services import profile_service


def is_watch_case(actor_goal: str | None, target_goal: str | None) -> bool:
    return target_goal == "CASUAL" and actor_goal != "CASUAL"


def record(db: Session, actor_id: uuid.UUID, target_id: uuid.UUID, *, is_super: bool = False, blocked: bool = False) -> bool:
    """감시 대상이면 기록하고 True. commit은 부르는 쪽에서."""
    actor_goal = profile_service.my_goal(db, actor_id)
    target_goal = profile_service.my_goal(db, target_id)
    if not is_watch_case(actor_goal, target_goal):
        return False
    now = utcnow()
    if blocked:
        # 막힌 버튼을 여러 번 누른 것은 1시간에 한 번만 센다
        recent = (
            db.query(WatchEvent.id)
            .filter(
                WatchEvent.user_id == actor_id,
                WatchEvent.target_user_id == target_id,
                WatchEvent.blocked.is_(True),
                WatchEvent.created_at >= now - timedelta(hours=1),
            )
            .first()
        )
        if recent is not None:
            return False
    db.add(
        WatchEvent(
            user_id=actor_id, target_user_id=target_id, actor_goal=actor_goal, is_super=is_super, blocked=blocked, created_at=now
        )
    )
    row = db.get(WatchTarget, actor_id)
    if row is None:
        db.add(WatchTarget(user_id=actor_id, status="WATCHING", event_count=1, first_at=now, last_at=now, updated_at=now))
    else:
        row.event_count = (row.event_count or 0) + 1
        row.last_at = now
        row.status = "WATCHING"  # '문제없음'으로 둔 사람도 다시 보내면 다시 지켜본다
    return True


def watching_ids(db: Session, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    """관리자 사용자 목록 표시용: user_id → 상태."""
    if not user_ids:
        return {}
    return {uid: st for uid, st in db.query(WatchTarget.user_id, WatchTarget.status).filter(WatchTarget.user_id.in_(user_ids))}
