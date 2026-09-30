"""공개 프로필 카드 만들기 + 매칭 엔진용 데이터 모으기.

다른 사용자에게 보내는 데이터는 반드시 build_cards()를 거친다.
이 함수는 설계도 §36에 나온 비공개 필드를 절대 넣지 않는다.
"""

import uuid
from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.time import age_on, kst_day_start
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
from app.models.user import User
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


def people_from_profiles(db: Session, profiles: list[PublicProfile]) -> list[Person]:
    user_ids = [p.user_id for p in profiles]
    prefs = preferences_of(db, user_ids)
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


def excluded_user_ids(db: Session, user_id: uuid.UUID) -> set[uuid.UUID]:
    """추천에서 빼야 할 사람: 이미 LIKE/PASS한 사람, 차단 관계(양방향), 매칭 이력이 있는 사람."""
    ids: set[uuid.UUID] = {user_id}
    ids.update(r[0] for r in db.query(Like.to_user_id).filter(Like.from_user_id == user_id))
    ids.update(r[0] for r in db.query(Block.blocked_user_id).filter(Block.blocker_user_id == user_id))
    ids.update(r[0] for r in db.query(Block.blocker_user_id).filter(Block.blocked_user_id == user_id))
    for a, b in db.query(Match.user_a_id, Match.user_b_id).filter((Match.user_a_id == user_id) | (Match.user_b_id == user_id)):
        ids.update((a, b))
    return ids


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
    return Weights(interest=s.weight_interest, completeness=s.weight_completeness, mbti=s.weight_mbti)


def current_tier(db: Session, user_id: uuid.UUID) -> str | None:
    """가장 최근 외모 평가의 등급 (내부 전용 — API 응답에 넣지 말 것)."""
    evaluation = latest_evaluations(db, [user_id]).get(user_id)
    return evaluation.tier if evaluation else None


def liked_me_ids(db: Session, user_id: uuid.UUID) -> set[uuid.UUID]:
    """나에게 LIKE를 보낸 사람들 (추천 우대용, 사용자에게는 절대 알려주지 않는다)."""
    return {r[0] for r in db.query(Like.from_user_id).filter(Like.to_user_id == user_id, Like.action == "LIKE")}


def likes_sent_today(db: Session, user_id: uuid.UUID) -> int:
    """오늘(한국 시간 0시 이후) 보낸 LIKE 수.

    LIKE는 항상 새 행으로 생긴다 (이미 LIKE/PASS한 상대에게는 다시 LIKE할 수 없음 → excluded_user_ids).
    PASS를 취소하면 행이 지워지므로, 그 뒤의 LIKE도 새 행이다. 그래서 created_at으로 셀 수 있다.
    """
    return (
        db.query(func.count(Like.id))
        .filter(Like.from_user_id == user_id, Like.action == "LIKE", Like.created_at >= kst_day_start())
        .scalar()
        or 0
    )


def likes_left_today(db: Session, user_id: uuid.UUID) -> int:
    return max(0, get_settings().daily_like_limit - likes_sent_today(db, user_id))


def count(db: Session, query) -> int:
    return db.query(func.count()).select_from(query.subquery()).scalar() or 0
