"""공개 프로필 카드 만들기 + 매칭 엔진용 데이터 모으기.

다른 사용자에게 보내는 데이터는 반드시 build_cards()를 거친다.
이 함수는 설계도 §36에 나온 비공개 필드를 절대 넣지 않는다.
"""

import uuid
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.time import age_on, as_utc, kst_day_start, kst_today, utcnow
from app.models.matching import (
    Block,
    Like,
    Match,
    MatchingPreference,
    PreferredCampus,
)
from app.models.photo import AppearanceEvaluation, UserPhoto
from app.models.profile import Interest, PrivateProfile, PublicProfile, UserInterest
from app.models.university import Campus, Department
from app.models.user import User, UserDailyVisit
from app.services.matching_service import Person, Preferences


# ---------- 여러 명의 정보를 한 번에 불러오기 ----------

def latest_evaluations(db: Session, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, AppearanceEvaluation]:
    """사람마다 가장 최근 외모 평가 1개.

    예전에는 평가 이력을 전부 불러와서 파이썬에서 마지막 것만 남겼다 → 재평가가 쌓일수록 느려짐.
    지금은 DB가 사람별로 최신 1개만 골라서 돌려준다 (ROW_NUMBER: 사람별로 최신순 번호를 매겨 1번만 가져오기).
    """
    if not user_ids:
        return {}
    ranked = (
        select(
            AppearanceEvaluation.id,
            func.row_number()
            .over(
                partition_by=AppearanceEvaluation.user_id,
                order_by=(AppearanceEvaluation.created_at.desc(), AppearanceEvaluation.id.desc()),
            )
            .label("rn"),
        )
        .where(AppearanceEvaluation.user_id.in_(user_ids))
        .subquery()
    )
    rows = (
        db.query(AppearanceEvaluation)
        .join(ranked, ranked.c.id == AppearanceEvaluation.id)
        .filter(ranked.c.rn == 1)
        .all()
    )
    return {row.user_id: row for row in rows}


def interests_of(db: Session, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[str]]:
    result: dict[uuid.UUID, list[str]] = defaultdict(list)
    if not user_ids:
        return result
    rows = (
        db.query(UserInterest.user_id, Interest.name)
        .join(Interest, Interest.id == UserInterest.interest_id)
        .filter(UserInterest.user_id.in_(user_ids))
        .order_by(Interest.name)
        .all()
    )
    for user_id, name in rows:
        result[user_id].append(name)
    return result


def birth_dates_of(db: Session, user_ids: list[uuid.UUID]) -> dict:
    if not user_ids:
        return {}
    rows = db.query(PrivateProfile.user_id, PrivateProfile.birth_date).filter(PrivateProfile.user_id.in_(user_ids)).all()
    return dict(rows)


def build_cards(db: Session, profiles: list[PublicProfile]) -> list[dict]:
    """다른 사용자에게 보여줄 공개 카드 목록 (설계도 §12, §20)."""
    user_ids = [p.user_id for p in profiles]
    evaluations = latest_evaluations(db, user_ids)
    interests = interests_of(db, user_ids)
    births = birth_dates_of(db, user_ids)
    campus_ids = {p.campus_id for p in profiles if p.show_campus}
    campus_names = dict(db.query(Campus.id, Campus.name).filter(Campus.id.in_(campus_ids)).all()) if campus_ids else {}
    dept_ids = {p.department_id for p in profiles if p.department_id and p.show_department}
    dept_names = dict(db.query(Department.id, Department.name).filter(Department.id.in_(dept_ids)).all()) if dept_ids else {}

    cards = []
    for p in profiles:
        evaluation = evaluations.get(p.user_id)
        cards.append(
            {
                "profile_id": str(p.id),
                "nickname": p.nickname,
                "age": age_on(births[p.user_id]) if p.user_id in births else None,
                "gender": p.gender,
                # 캠퍼스·학과는 본인이 공개로 고른 경우에만 보낸다 (고르지 않았으면 숨김)
                "campus": campus_names.get(p.campus_id) if p.show_campus else None,
                "department": dept_names.get(p.department_id) if p.show_department else None,
                "mbti": p.mbti,
                "bio": p.bio,
                "ideal_type": p.ideal_type,
                "interests": interests.get(p.user_id, []),
                "appearance": evaluation.scores() if evaluation else None,
            }
        )
    return cards


def build_card(db: Session, profile: PublicProfile) -> dict:
    return build_cards(db, [profile])[0]


# ---------- 매칭 엔진용 ----------

def preferred_genders_of(db: Session, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    """원하는 성별 (가입할 때 정한 값, PrivateProfile에 있음)."""
    if not user_ids:
        return {}
    rows = db.query(PrivateProfile.user_id, PrivateProfile.preferred_gender).filter(PrivateProfile.user_id.in_(user_ids)).all()
    return dict(rows)


def preferences_of(db: Session, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, Preferences]:
    """매칭 조건. 매칭 조건 화면에서 저장한 적이 없으면(행이 없으면) 결과에 없다."""
    if not user_ids:
        return {}
    prefs = db.query(MatchingPreference).filter(MatchingPreference.user_id.in_(user_ids)).all()
    genders = preferred_genders_of(db, [p.user_id for p in prefs])
    campuses = defaultdict(set)
    for uid, cid in db.query(PreferredCampus.user_id, PreferredCampus.campus_id).filter(PreferredCampus.user_id.in_(user_ids)):
        campuses[uid].add(cid)
    return {
        p.user_id: Preferences(
            preferred_gender=genders.get(p.user_id, "ANY"),
            min_age=p.min_age,
            max_age=p.max_age,
            campus_mode=p.campus_mode,
            campus_ids=campuses[p.user_id],
            exclude_same_department=p.exclude_same_department,
        )
        for p in prefs
    }


def activity_of(db: Session, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, float]:
    """활동 점수 0~1 = 최근 N일(오늘 포함, 한국 시간) 중 접속한 날 수 ÷ N.

    사람 수만큼 DB를 부르지 않도록 한 번에 센다 (하루 한 줄이라 가볍다).
    """
    if not user_ids:
        return {}
    days = get_settings().activity_window_days
    since = kst_today() - timedelta(days=days - 1)
    rows = (
        db.query(UserDailyVisit.user_id, func.count())
        .filter(UserDailyVisit.user_id.in_(user_ids), UserDailyVisit.visit_date >= since)
        .group_by(UserDailyVisit.user_id)
        .all()
    )
    return {uid: min(n / days, 1.0) for uid, n in rows}


def people_from_profiles(db: Session, profiles: list[PublicProfile]) -> list[Person]:
    user_ids = [p.user_id for p in profiles]
    prefs = preferences_of(db, user_ids)
    activity = activity_of(db, user_ids)
    births = birth_dates_of(db, user_ids)
    interests = interests_of(db, user_ids)
    evaluations = latest_evaluations(db, user_ids)
    people = []
    for p in profiles:
        if p.user_id not in births:
            continue
        evaluation = evaluations.get(p.user_id)
        people.append(
            Person(
                user_id=p.user_id,
                gender=p.gender,
                age=age_on(births[p.user_id]),
                campus_id=p.campus_id,
                department_id=p.department_id,
                preferences=prefs.get(p.user_id),
                interests=set(interests.get(p.user_id, [])),
                mbti=p.mbti,
                has_bio=bool(p.bio),
                has_ideal_type=bool(p.ideal_type),
                tier=evaluation.tier if evaluation else None,
                activity=activity.get(p.user_id, 0.0),
            )
        )
    return people


def has_approved_photo(db: Session, user_id: uuid.UUID) -> bool:
    return (
        db.query(UserPhoto.id)
        .filter(UserPhoto.user_id == user_id, UserPhoto.review_status == "APPROVED")
        .first()
        is not None
    )


def has_pending_photo(db: Session, user_id: uuid.UUID) -> bool:
    """검수를 기다리는 사진(대기·확인 중)이 있는지."""
    return (
        db.query(UserPhoto.id)
        .filter(
            UserPhoto.user_id == user_id,
            UserPhoto.review_status.in_(["PENDING", "IN_REVIEW"]),
            UserPhoto.upload_status != "DELETED",
        )
        .first()
        is not None
    )


def discoverable_profiles_query(db: Session, university_id: uuid.UUID):
    """추천 후보가 될 수 있는 프로필: 활성 계정 + 같은 학교 + 승인된 사진 + 외모 등급 + 매칭 조건 설정.

    외모 등급은 "가장 최근 평가"에 있어야 한다 → 등급 없는 예전 평가만 있는 사람은
    추천 엔진(people_from_profiles → tier=None)에서 가장 뒤로 가고, API에서 한 번 더 거른다.
    """
    approved = db.query(UserPhoto.user_id).filter(UserPhoto.review_status == "APPROVED")
    evaluated = db.query(AppearanceEvaluation.user_id).filter(AppearanceEvaluation.tier.isnot(None))
    with_prefs = db.query(MatchingPreference.user_id)
    return (
        db.query(PublicProfile)
        .join(User, User.id == PublicProfile.user_id)
        .filter(
            User.status == "ACTIVE",
            User.university_id == university_id,
            PublicProfile.profile_status == "ACTIVE",
            PublicProfile.user_id.in_(approved),
            PublicProfile.user_id.in_(evaluated),
            PublicProfile.user_id.in_(with_prefs),
        )
    )


def is_vip_tester(user: User) -> bool:
    """VIP 테스트 계정인가? (설정 VIP_TEST_EMAILS에 적힌 학교 메일, 2026-10-02)"""
    return (user.email or "").strip().lower() in get_settings().vip_test_email_set


def _pass_cutoff() -> datetime:
    """이 시각 이후에 PASS한 사람은 아직 추천에서 뺀다 (PASS 후 pass_cooldown_hours 동안)."""
    return utcnow() - timedelta(hours=get_settings().pass_cooldown_hours)


def vip_tester_ids(db: Session) -> set[uuid.UUID]:
    """VIP 테스트 계정들의 user_id (이메일은 가입할 때 소문자로 저장된다)."""
    emails = get_settings().vip_test_email_set
    if not emails:
        return set()
    return {r[0] for r in db.query(User.id).filter(func.lower(User.email).in_(emails))}


# 서버가 켜진 시각 (= 이 업데이트를 배포한 시각).
# 이보다 먼저 VIP 테스트 계정을 PASS한 기록은 무시한다 → 배포하자마자 모두에게 다시 추천된다.
VIP_PASS_RESET_FROM = utcnow()


def _pass_still_hides(to_id: uuid.UUID, passed_at, vip_ids: set[uuid.UUID]) -> bool:
    """이 PASS가 아직 상대를 추천에서 숨기는가?

    - 일반 사용자에게 한 PASS: 48시간(pass_cooldown_hours) 동안
    - VIP 테스트 계정에 한 PASS: 그날 하루(한국 시간 자정까지)만, 그리고 서버가 켜진 뒤에 한 것만 (2026-10-02)
    """
    if passed_at is None:
        return False
    passed_at = as_utc(passed_at)
    if to_id in vip_ids:
        return passed_at >= max(kst_day_start(), VIP_PASS_RESET_FROM)
    return passed_at > _pass_cutoff()


def _passes(db: Session, user_id: uuid.UUID):
    return db.query(Like.to_user_id, Like.updated_at).filter(Like.from_user_id == user_id, Like.action == "PASS")


def excluded_user_ids(db: Session, user_id: uuid.UUID, *, include_passed: bool = True) -> set[uuid.UUID]:
    """추천에서 빼야 할 사람: 이미 LIKE한 사람, 최근에 PASS한 사람, 차단 관계(양방향), 매칭 이력이 있는 사람.

    PASS는 영원히 빼지 않는다 (2026-10-02). 베타라 사람이 적어서 추천이 금방 바닥나기 때문.
    - 보통: PASS 후 48시간 동안만 뺀다
    - VIP 테스트 계정을 PASS한 경우: 그날 하루만 뺀다 → 매일 다시 추천된다
    PASS 시각은 updated_at으로 본다 (같은 사람을 다시 PASS하면 그때 시각으로 바뀐다 → _upsert_action).
    업데이트 전에 남긴 PASS도 updated_at이 있으므로 같은 규칙이 그대로 적용된다.

    include_passed=False: PASS한 사람은 빼지 않는다 (VIP 테스트 계정 본인 — PASS해도 다시 나옴).
    """
    ids: set[uuid.UUID] = {user_id}
    ids.update(r[0] for r in db.query(Like.to_user_id).filter(Like.from_user_id == user_id, Like.action == "LIKE"))
    if include_passed:
        vip_ids = vip_tester_ids(db)
        ids.update(to_id for to_id, at in _passes(db, user_id) if _pass_still_hides(to_id, at, vip_ids))
    ids.update(r[0] for r in db.query(Block.blocked_user_id).filter(Block.blocker_user_id == user_id))
    ids.update(r[0] for r in db.query(Block.blocker_user_id).filter(Block.blocked_user_id == user_id))
    for a, b in db.query(Match.user_a_id, Match.user_b_id).filter((Match.user_a_id == user_id) | (Match.user_b_id == user_id)):
        ids.update((a, b))
    return ids


def passed_before_ids(db: Session, user_id: uuid.UUID) -> set[uuid.UUID]:
    """예전에 PASS했지만 이제 다시 추천될 수 있는 사람. 추천 순서에서 "처음 보는 사람" 뒤로 보낸다."""
    vip_ids = vip_tester_ids(db)
    return {to_id for to_id, at in _passes(db, user_id) if not _pass_still_hides(to_id, at, vip_ids)}


def is_blocked_between(db: Session, a: uuid.UUID, b: uuid.UUID) -> bool:
    return (
        db.query(Block.id)
        .filter(
            ((Block.blocker_user_id == a) & (Block.blocked_user_id == b))
            | ((Block.blocker_user_id == b) & (Block.blocked_user_id == a))
        )
        .first()
        is not None
    )


def blocked_user_ids(db: Session, user_id: uuid.UUID) -> set[uuid.UUID]:
    """나와 차단 관계인 사람 전부 (내가 차단했든, 상대가 나를 차단했든). 쿼리 1번."""
    rows = db.query(Block.blocker_user_id, Block.blocked_user_id).filter(
        (Block.blocker_user_id == user_id) | (Block.blocked_user_id == user_id)
    )
    return {blocked if blocker == user_id else blocker for blocker, blocked in rows}


def find_active_profile(db: Session, profile_id: uuid.UUID) -> PublicProfile | None:
    return (
        db.query(PublicProfile)
        .join(User, User.id == PublicProfile.user_id)
        .filter(PublicProfile.id == profile_id, User.status == "ACTIVE", PublicProfile.profile_status == "ACTIVE")
        .first()
    )


def match_pair(a: uuid.UUID, b: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    return (a, b) if str(a) < str(b) else (b, a)


def matching_weights():
    from app.services.matching_service import Weights

    s = get_settings()
    return Weights(
        interest=s.weight_interest,
        completeness=s.weight_completeness,
        mbti=s.weight_mbti,
        activity=s.weight_activity,
    )


def current_tier(db: Session, user_id: uuid.UUID) -> str | None:
    """가장 최근 외모 평가의 등급 (내부 전용 — API 응답에 넣지 말 것)."""
    evaluation = latest_evaluations(db, [user_id]).get(user_id)
    return evaluation.tier if evaluation else None


def liked_me_ids(db: Session, user_id: uuid.UUID) -> set[uuid.UUID]:
    """나에게 LIKE를 보낸 사람들 (추천 우대용, 사용자에게는 절대 알려주지 않는다)."""
    return {r[0] for r in db.query(Like.from_user_id).filter(Like.to_user_id == user_id, Like.action == "LIKE")}


def likes_sent_today(db: Session, user_id: uuid.UUID) -> int:
    """오늘(한국 시간 0시 이후) 보낸 LIKE 수.

    LIKE는 항상 새 행으로 생긴다 (이미 LIKE한 상대에게는 다시 LIKE할 수 없음 → excluded_user_ids).
    PASS 48시간이 지나 다시 나온 사람에게 LIKE하면, PASS 행을 지우고 새 행을 만든다 (_upsert_action).
    PASS를 취소해도 행이 지워진다. 그래서 created_at으로 셀 수 있다.
    """
    return (
        db.query(func.count(Like.id))
        .filter(Like.from_user_id == user_id, Like.action == "LIKE", Like.created_at >= kst_day_start())
        .scalar()
        or 0
    )


def likes_left_today(db: Session, user_id: uuid.UUID, *, unlimited: bool = False) -> int:
    limit = get_settings().daily_like_limit
    if unlimited:
        # VIP 테스트 계정: 화면의 하트가 줄지 않도록 항상 "가득 참"으로 보낸다
        return limit
    return max(0, limit - likes_sent_today(db, user_id))


def count(db: Session, query) -> int:
    return db.query(func.count()).select_from(query.subquery()).scalar() or 0
