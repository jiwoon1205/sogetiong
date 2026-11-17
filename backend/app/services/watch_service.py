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


# ---------- 모니터링 숫자 (2026-11-17) ----------
# 저장해 두지 않고 볼 때마다 DB에서 센다 → 예전 기록(감시 기능 전 좋아요·매칭)까지 항상 최신으로 보인다.
# "캐주얼" = 캐주얼한 만남을 한 번이라도 고른 사람 (찾는 관계 변경 기록 + 지금 값, profile_service.ever_casual_*).
# 캐주얼이 보낸 슈퍼 라이크를 받아서 어쩔 수 없이 생긴 매칭은 세지 않는다 (2026-11-17 사용자 결정).
# 반대로 이 사람이 캐주얼에게 슈퍼 라이크를 보낸 매칭은 센다.


def received_super_from(match, me) -> bool:
    """상대(캐주얼)가 보낸 슈퍼 라이크로 생긴 매칭인가 → 감시 숫자에서 뺀다."""
    return match.super_like_by is not None and match.super_like_by != me


def _casual_set(db: Session) -> set[uuid.UUID]:
    return {uid for (uid,) in profile_service.ever_casual_query(db)}


def casual_stats(db: Session, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict]:
    """감시 대상마다: 캐주얼과 매칭 수(내가 먼저 시작한 수·슈퍼 라이크 보낸 수), 캐주얼에게 보낸 좋아요 수, 좋아요 보낸 캐주얼 수, 막힌 시도 수."""
    from sqlalchemy import func, or_

    from app.models.matching import Like, Match

    ids = set(user_ids)
    out = {
        uid: {"casual_matches": 0, "casual_matches_started": 0, "casual_super_likes": 0, "casual_likes": 0, "casual_liked_people": 0, "blocked": 0}
        for uid in ids
    }
    if not ids:
        return out
    casual = _casual_set(db)

    likes = db.query(Like.from_user_id, Like.to_user_id, Like.like_count, Like.created_at).filter(
        Like.from_user_id.in_(ids), Like.like_count > 0
    )
    for frm, to, n, _ in likes:
        if to in casual:
            out[frm]["casual_likes"] += n or 0
            out[frm]["casual_liked_people"] += 1

    # 매칭: 누가 먼저 시작했나 = 슈퍼 라이크 보낸 사람, 아니면 먼저 좋아요한 사람
    matches = db.query(Match).filter(or_(Match.user_a_id.in_(ids), Match.user_b_id.in_(ids))).all()
    first_like: dict[tuple, object] = {}
    if matches:
        pairs = {(m.user_a_id, m.user_b_id) for m in matches} | {(m.user_b_id, m.user_a_id) for m in matches}
        froms = {a for a, _ in pairs}
        for frm, to, at in db.query(Like.from_user_id, Like.to_user_id, Like.created_at).filter(
            Like.from_user_id.in_(froms), Like.action == "LIKE"
        ):
            if (frm, to) in pairs:
                first_like[(frm, to)] = at
    for m in matches:
        for me, partner in ((m.user_a_id, m.user_b_id), (m.user_b_id, m.user_a_id)):
            if me not in ids or partner not in casual or received_super_from(m, me):
                continue
            row = out[me]
            row["casual_matches"] += 1
            if m.super_like_by == me:
                row["casual_super_likes"] += 1
                row["casual_matches_started"] += 1
            elif m.super_like_by is None:
                mine, theirs = first_like.get((me, partner)), first_like.get((partner, me))
                if mine is not None and (theirs is None or mine <= theirs):
                    row["casual_matches_started"] += 1

    for uid, n in (
        db.query(WatchEvent.user_id, func.count(WatchEvent.id))
        .filter(WatchEvent.user_id.in_(ids), WatchEvent.blocked.is_(True))
        .group_by(WatchEvent.user_id)
    ):
        out[uid]["blocked"] = n
    return out


def qualifies(stats: dict) -> bool:
    """감시할 이유가 있나: 캐주얼과 매칭(받은 슈퍼 라이크 제외) / 캐주얼에게 좋아요 / 막힌 시도 중 하나라도."""
    return stats["casual_matches"] > 0 or stats["casual_likes"] > 0 or stats["blocked"] > 0


def casual_detail(db: Session, user_id: uuid.UUID) -> dict:
    """한 사람의 캐주얼 매칭 목록과 캐주얼에게 보낸 좋아요 목록."""
    from sqlalchemy import or_

    from app.models.matching import Like, Match, Message

    casual = _casual_set(db)
    matches = [
        m
        for m in db.query(Match).filter(or_(Match.user_a_id == user_id, Match.user_b_id == user_id)).order_by(Match.created_at.desc())
        if (m.user_b_id if m.user_a_id == user_id else m.user_a_id) in casual and not received_super_from(m, user_id)
    ]
    my_msgs: dict = {}
    if matches:
        for mid, sender in db.query(Message.match_id, Message.sender_user_id).filter(Message.match_id.in_([m.id for m in matches])):
            if sender == user_id:
                my_msgs[mid] = my_msgs.get(mid, 0) + 1
    likes_to = {
        to: (n, at, sup)
        for to, n, at, sup in db.query(Like.to_user_id, Like.like_count, Like.created_at, Like.is_super).filter(
            Like.from_user_id == user_id, Like.like_count > 0
        )
        if to in casual
    }
    likes_from = {
        frm: at
        for frm, at in db.query(Like.from_user_id, Like.created_at).filter(Like.to_user_id == user_id, Like.action == "LIKE")
        if frm in casual
    }
    match_rows = []
    for m in matches:
        partner = m.user_b_id if m.user_a_id == user_id else m.user_a_id
        if m.super_like_by is not None:  # 받은 슈퍼 라이크는 위에서 뺐으므로 여기는 내가 보낸 것
            started = "me"
            how = "슈퍼 라이크 (보냄)"
        else:
            how = "좋아요 5번" if m.by_repeat_likes else "서로 좋아요"
            mine = likes_to.get(partner, (None, None, None))[1]
            theirs = likes_from.get(partner)
            started = "me" if mine is not None and (theirs is None or mine <= theirs) else ("them" if theirs is not None else None)
        match_rows.append(
            {
                "partner_id": partner,
                "at": m.created_at,
                "how": how,
                "started": started,
                "my_messages": my_msgs.get(m.id, 0),
                "status": m.status,
            }
        )
    like_rows = [
        {"partner_id": to, "count": n, "last_at": at, "is_super": bool(sup)}
        for to, (n, at, sup) in sorted(likes_to.items(), key=lambda kv: kv[1][1], reverse=True)
    ]
    return {"matches": match_rows, "likes": like_rows}
