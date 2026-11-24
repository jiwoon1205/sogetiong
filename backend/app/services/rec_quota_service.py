"""좋아요가 3·4번 쌓인 사람의 추천 노출 제한 (2026-11-13).

⚠️ 내부 규칙이다. 사용자 화면·API 응답 어디에도 이 제한이나 남은 자리 수를 내보내지 않는다.
   자리가 없어 빠진 사람은 "원래 추천에 안 나오는 사람"과 똑같이 그냥 목록에 없다.

왜: 좋아요를 같은 사람에게 5번 보내면 바로 매칭된다(2026-10-24). 이 길로 생기는 매칭이 많아 슈퍼 라이크를 살 이유가 줄었다.

규칙
- 이용권 기간마다 "내가 좋아요를 3번 보낸 사람"은 REC_QUOTA_LEVEL3명(4), "4번 보낸 사람"은 REC_QUOTA_LEVEL4명(2)까지만
  추천에 나온다. 서로 다른 사람 수로 센다. 처음 추천 페이지에 실제로 나온 순간 자리를 차지하고(rec_quota_slots),
  자리를 받은 사람은 그 기간 동안 계속 나올 수 있다. 3번 자리를 받은 사람에게 좋아요를 한 번 더 보내면 4번 자리가 따로 필요하다.
- 이용권·VIP 입금이 확인되면 자리를 모두 비운다 (reset, admin.confirm_payment) → 다시 4명·2명.
- 이용권이 끝나 좋아요를 못 하는 사람(like_access == "none"): 4번 보낸 사람은 REC_QUOTA_TEASER명(1)만 추천 맨 앞에 보여 준다 (맛보기).
  좋아요를 누르면 지금처럼 결제 안내가 뜬다. 3번 보낸 사람은 위와 같은 자리 규칙.
- 여성 회원·VIP 테스트 계정·슈퍼 VIP는 제한 없음 (applies).

2026-11-24 추가 (사용자 결정)
- 이용권이 끝난 사람: 맨 앞 맛보기 = 조건이 맞는 사람 중 **내가 좋아요를 가장 많이 보낸 사람 1명** (2번 이상, REC_TEASER_MIN_SENT).
  추첨에 뽑혔는지와 상관없이 전체에서 고른다 (pick_teaser). 결제를 유도하려는 것.
- 이번 이용권 기간에 매칭이 REC_HEAVY_MATCHES회(5) 이상인 사람(heavy_matcher):
  · 좋아요 3번 쌓인 사람은 뽑힐 확률 × REC_HEAVY_THREE_FACTOR(0.2) (matching_service.Weights.sent_three_factor)
  · 좋아요 4번 쌓인 사람은 이용권 기간 동안 **1명, 자리를 받은 그날 하루만** 나온다.
  이용권 기간 시작 = 마지막으로 이용권·VIP 입금이 확인된 때 (없으면 가입한 때).
- 좋아요 3번 미만인 사람과 슈퍼 VIP 자리는 건드리지 않는다.
"""

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from sqlalchemy import func, or_

from app.core.config import get_settings
from app.core.time import as_utc, kst_today, utcnow
from app.models.matching import Match, RecQuotaSlot
from app.models.payment import Payment
from app.models.user import User
from app.services import vip_service


def applies(user: User) -> bool:
    if not get_settings().rec_quota_enabled:
        return False
    if vip_service.is_vip_tester(user):  # VIP 테스트 계정·슈퍼 VIP
        return False
    return vip_service.gender_of(user) != "FEMALE"


def period_start(db: Session, user: User):
    """이번 이용권 기간이 시작된 때: 마지막으로 이용권·VIP 입금이 확인된 시각 (슈퍼 라이크 제외). 없으면 가입한 때."""
    last = (
        db.query(func.max(Payment.processed_at))
        .filter(Payment.user_id == user.id, Payment.status == "CONFIRMED", Payment.kind != "SUPER_LIKE")
        .scalar()
    )
    return last or user.created_at


def heavy_matcher(db: Session, user: User) -> bool:
    """이번 이용권 기간에 매칭이 REC_HEAVY_MATCHES회 이상 (2026-11-24). 제한 대상(applies)인 사람만."""
    n = get_settings().rec_heavy_matches
    if n <= 0 or not applies(user):
        return False
    start = period_start(db, user)
    count = (
        db.query(func.count(Match.id))
        .filter(or_(Match.user_a_id == user.id, Match.user_b_id == user.id), Match.created_at >= start)
        .scalar()
    )
    return (count or 0) >= n


def pick_teaser(people: list, sent_counts: dict[uuid.UUID, int], is_ok, seed: str):
    """이용권이 끝난 사람의 맨 앞 맛보기: 좋아요를 가장 많이 보낸 사람 (REC_TEASER_MIN_SENT번 이상). 없으면 None.
    같은 횟수면 날마다 정해진 순서(seed)로 고른다. is_ok(person) = 서로 조건이 맞는지."""
    least = max(get_settings().rec_teaser_min_sent, 1)
    best = [p for p in people if sent_counts.get(p.user_id, 0) >= least and is_ok(p)]
    if not best:
        return None
    from app.services.matching_service import seeded_uniform

    return max(best, key=lambda p: (sent_counts.get(p.user_id, 0), seeded_uniform(seed, p.user_id)))


def _level(count: int) -> int | None:
    """보낸 좋아요 횟수 → 3 / 4 / None(제한 대상 아님). 5번이면 이미 매칭이라 추천에 없다."""
    if count >= 4:
        return 4
    if count == 3:
        return 3
    return None


def extra_candidates(sent_counts: dict[uuid.UUID, int]) -> int:
    """자리가 없어 빠질 수 있는 사람 수. 페이지가 모자라지 않게 그만큼 더 뽑아 둔다."""
    return sum(1 for c in sent_counts.values() if _level(c) is not None)


def apply(
    db: Session,
    user: User,
    ranked: list,
    sent_counts: dict[uuid.UUID, int],
    limit: int,
    *,
    can_like: bool,
    teaser=None,
    heavy: bool = False,
) -> list:
    """가중치 추첨 결과(ranked, limit보다 넉넉히 뽑은 것)에서 자리 없는 사람을 빼고 limit명으로 자른다.

    ranked의 각 항목은 user_id 속성이 있으면 된다 (matching_service.Person).
    새로 자리를 받은 사람은 이 함수가 기록한다 (commit은 save에서).
    """
    if not applies(user):
        return ranked[:limit]
    s = get_settings()
    caps = {3: max(s.rec_quota_level3, 0), 4: max(s.rec_quota_level4, 0)}
    if heavy:
        caps[4] = min(caps[4], 1)  # 매칭이 많은 사람: 4번 쌓인 사람은 기간 동안 1명만 (2026-11-24)
    rows = db.query(RecQuotaSlot.target_user_id, RecQuotaSlot.level, RecQuotaSlot.created_at).filter(
        RecQuotaSlot.user_id == user.id
    )
    today = kst_today(utcnow())
    have: set[tuple[uuid.UUID, int]] = set()
    expired: set[tuple[uuid.UUID, int]] = set()  # 매칭이 많은 사람: 4번 자리는 받은 그날 하루만
    for t, lv, at in rows:
        have.add((t, lv))
        if heavy and lv == 4 and kst_today(as_utc(at)) != today:
            expired.add((t, lv))
    used = {3: sum(1 for _, lv in have if lv == 3), 4: sum(1 for _, lv in have if lv == 4)}

    # 이용권이 끝남: 맨 앞 맛보기 1명 = 좋아요를 가장 많이 보낸 사람 (2026-11-24, pick_teaser). 자리는 쓰지 않는다
    teasers: list = [teaser] if (teaser is not None and not can_like and s.rec_quota_teaser > 0) else []
    teaser_id = teasers[0].user_id if teasers else None
    page: list = []
    new_slots: set[tuple[uuid.UUID, int]] = set()
    for p in ranked:
        if p.user_id == teaser_id:
            continue
        level = _level(sent_counts.get(p.user_id, 0))
        if level is None:
            page.append(p)
            continue
        if level == 4 and not can_like:
            continue  # 이용권이 끝남: 4번 보낸 다른 사람은 안 나온다
        key = (p.user_id, level)
        if key in expired:
            continue
        if key in have:
            page.append(p)
        elif used[level] < caps[level]:
            used[level] += 1
            new_slots.add(key)
            page.append(p)
        # 자리가 없으면 뺀다

    final = (teasers + page)[:limit]
    shown = {p.user_id for p in final}
    for target, level in new_slots:
        if target in shown:  # 실제로 페이지에 나간 사람만 자리를 차지한다
            db.add(RecQuotaSlot(user_id=user.id, target_user_id=target, level=level))
    return final


def save(db: Session) -> None:
    """새 자리를 저장한다. 같은 사람이 동시에 추천을 두 번 열어 같은 자리가 겹치면 이번 기록은 버린다 (다음에 다시 기록됨)."""
    if not db.new:
        return
    try:
        db.commit()
    except IntegrityError:
        db.rollback()


def reset(db: Session, user_id: uuid.UUID) -> None:
    """이용권·VIP를 새로 샀다 → 자리를 모두 비운다. commit은 부르는 쪽에서."""
    db.query(RecQuotaSlot).filter(RecQuotaSlot.user_id == user_id).delete(synchronize_session=False)
