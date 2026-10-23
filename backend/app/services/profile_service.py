"""공개 프로필 카드 만들기 + 매칭 엔진용 데이터 모으기.

다른 사용자에게 보내는 데이터는 반드시 build_cards()를 거친다.
이 함수는 설계도 §36에 나온 비공개 필드를 절대 넣지 않는다.
"""

import uuid
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import func, or_, select
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
from app.models.university import Campus, Department, University
from app.models.user import User, UserDailyVisit
from app.services import vip_service
from app.services.matching_service import Person, Preferences, text_chars


# ---------- 학교 (2026-10-24 경희대 확장) ----------
# 열린 학교(universities.active, 설정 OPEN_SCHOOLS로 켬)끼리는 서로 추천에 나온다.
# 닫힌 학교 사람(열기 전 테스트 계정)은 같은 학교 사람과 VIP 테스트 계정하고만 서로 보인다.

def open_university_ids(db: Session) -> set[uuid.UUID]:
    return {uid for (uid,) in db.query(University.id).filter(University.active.is_(True))}


def multi_school(db: Session) -> bool:
    """열린 학교가 둘 이상인가? → 카드에 학교 이름을 보여 주고, 캠퍼스는 항상 공개한다 (2026-10-23 결정)."""
    return len(open_university_ids(db)) > 1


def visible_university_ids(db: Session, viewer: User) -> set[uuid.UUID]:
    """이 사람이 추천에서 볼 수 있는 학교 (매칭 조건 캠퍼스로 고를 수 있는 학교도 같다)."""
    open_ids = open_university_ids(db)
    if viewer.university_id not in open_ids:
        return {viewer.university_id}  # 닫힌 학교 테스트 계정: 자기 학교만 (+ VIP 테스트 계정, 아래 school_filter)
    if vip_service.is_test_account(viewer):
        return {uid for (uid,) in db.query(University.id)}  # 운영자 테스트 계정: 닫힌 학교 테스트 계정도 본다
    return open_ids


def _test_account_emails() -> list[str]:
    return sorted(get_settings().vip_test_email_set)


def school_filter(db: Session, viewer: User):
    """추천 후보 쿼리에 붙이는 학교 조건 (User 테이블 기준)."""
    condition = User.university_id.in_(visible_university_ids(db, viewer))
    if viewer.university_id not in open_university_ids(db) and _test_account_emails():
        condition = or_(condition, User.email.in_(_test_account_emails()))
    return condition


def school_visible(db: Session, viewer: User, target: User) -> bool:
    """LIKE·슈퍼 라이크를 ID로 직접 보낼 때도 추천과 같은 학교 규칙을 지킨다."""
    if target.university_id in visible_university_ids(db, viewer):
        return True
    return viewer.university_id not in open_university_ids(db) and vip_service.is_test_account(target)


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
    # 학교가 둘 이상 열려 있으면 학교 이름을 붙이고 캠퍼스는 항상 공개한다 (2026-10-23 결정).
    # 학교가 하나일 때는 예전과 똑같다 (학교 이름 없음, 캠퍼스는 본인이 고른 대로).
    # 닫힌 학교 테스트 계정이 섞여 있으면(운영자 테스트 중) 그때도 학교 이름을 붙인다.
    open_ids = open_university_ids(db)
    user_schools = (
        dict(db.query(User.id, User.university_id).filter(User.id.in_(user_ids)).all()) if user_ids else {}
    )
    show_school = len(open_ids) > 1 or any(u not in open_ids for u in user_schools.values())
    school_names = dict(db.query(University.id, University.name).all()) if show_school else {}
    campus_ids = {p.campus_id for p in profiles if p.show_campus or show_school}
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
                # 캠퍼스·학과는 본인이 공개로 고른 경우에만 보낸다 (고르지 않았으면 숨김).
                # 학교가 둘 이상 열리면 학교·캠퍼스는 항상 공개 (2026-10-23)
                "university": school_names.get(user_schools.get(p.user_id)) if show_school else None,
                "campus": campus_names.get(p.campus_id) if (p.show_campus or show_school) else None,
                "department": dept_names.get(p.department_id) if p.show_department else None,
                "mbti": p.mbti,
                "bio": p.bio,
                "ideal_type": p.ideal_type,
                # 본인이 고른 값 (AI 평가가 아님). 안 골랐으면 null
                "face_type": p.face_type,
                "height_cm": p.height_cm,
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
    all_campus_ids = set().union(*campuses.values()) if campuses else set()
    campus_school = (
        dict(db.query(Campus.id, Campus.university_id).filter(Campus.id.in_(all_campus_ids))) if all_campus_ids else {}
    )
    return {
        p.user_id: Preferences(
            preferred_gender=genders.get(p.user_id, "ANY"),
            min_age=p.min_age,
            max_age=p.max_age,
            campus_mode=p.campus_mode,
            campus_ids=campuses[p.user_id],
            exclude_same_department=p.exclude_same_department,
            university_ids={campus_school[c] for c in campuses[p.user_id] if c in campus_school},
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
    user_rows = db.query(User.id, User.super_vip, User.university_id).filter(User.id.in_(user_ids)).all() if user_ids else []
    supers = {uid for uid, sv, _ in user_rows if sv}
    schools = {uid: uni for uid, _, uni in user_rows}
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
                bio_chars=text_chars(p.bio),
                ideal_chars=text_chars(p.ideal_type),
                has_face_type=bool(p.face_type),
                has_height=p.height_cm is not None,
                tier=evaluation.tier if evaluation else None,
                activity=activity.get(p.user_id, 0.0),
                super_vip=p.user_id in supers,
                university_id=schools.get(p.user_id),
            )
        )
    return people


def approved_photo_filter():
    """"승인된 사진이 있다"의 기준 (2026-10-11): 승인 + 사진 파일이 아직 있음.

    탈퇴 7일 뒤 사진 파일은 지워지지만(withdrawal_service) 승인 기록은 남는다. 그 뒤에 재가입하면 그 기록이
    새 계정으로 옮겨져서, 예전에는 볼 수 있는 사진 없이 "사진 승인됨"으로 추천에 나왔다 (관리자도 사진을 볼 수 없음).
    → 파일이 지워진 사진은 승인된 사진으로 치지 않는다. 그런 사람은 새 사진을 올려야 한다."""
    return (
        UserPhoto.review_status == "APPROVED",
        UserPhoto.upload_status != "DELETED",
        UserPhoto.storage_key != "",
    )


def approved_photo_user_ids(db: Session):
    """볼 수 있는 승인 사진이 있는 사용자 ID (서브쿼리용)."""
    return db.query(UserPhoto.user_id).filter(*approved_photo_filter())


def has_approved_photo(db: Session, user_id: uuid.UUID) -> bool:
    return db.query(UserPhoto.id).filter(UserPhoto.user_id == user_id, *approved_photo_filter()).first() is not None


def photo_files_purged(db: Session, user_id: uuid.UUID) -> bool:
    """파일이 지워진 사진만 있고 볼 수 있는 사진이 하나도 없다 = 탈퇴 7일 뒤 사진 파일이 지워진 다음 재가입하고
    아직 새 사진을 안 낸 사람 (2026-10-11). 새 사진을 내면 첫 검수처럼 받는다 (재검토 대기·이용권 조건 없음)."""
    photos = db.query(UserPhoto.id).filter(UserPhoto.user_id == user_id)
    has_file = photos.filter(UserPhoto.upload_status != "DELETED", UserPhoto.storage_key != "").first() is not None
    return not has_file and photos.filter(UserPhoto.upload_status == "DELETED").first() is not None


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


def discoverable_profiles_query(db: Session, viewer: User, *, members_only: bool = True):
    """추천 후보가 될 수 있는 프로필: 활성 계정 + 볼 수 있는 학교 + 승인된 사진 + 외모 등급 + 매칭 조건 설정.

    학교 (2026-10-24): 예전에는 "같은 학교만"이었다. 지금은 열린 학교 전체 (school_filter).
    어느 학교·캠퍼스까지 볼지는 각자의 매칭 조건(캠퍼스)이 양쪽으로 정한다 (matching_service).

    외모 등급은 "가장 최근 평가"에 있어야 한다 → 등급 없는 예전 평가만 있는 사람은
    추천 엔진(people_from_profiles → tier=None)에서 가장 뒤로 가고, API에서 한 번 더 거른다.
    """
    approved = approved_photo_user_ids(db)
    evaluated = db.query(AppearanceEvaluation.user_id).filter(AppearanceEvaluation.tier.isnot(None))
    with_prefs = db.query(MatchingPreference.user_id)
    query = (
        db.query(PublicProfile)
        .join(User, User.id == PublicProfile.user_id)
        .filter(
            User.status == "ACTIVE",
            school_filter(db, viewer),
            PublicProfile.profile_status == "ACTIVE",
            PublicProfile.user_id.in_(approved),
            PublicProfile.user_id.in_(evaluated),
            PublicProfile.user_id.in_(with_prefs),
        )
    )
    # 2026-10-06 무료 체험: 이용권이 없거나 끝난 사람도 남의 추천에 나온다 ("체험 이용권도 이용권").
    # (예전 2026-10-04 D5 "이용권이 끝난 사람은 숨김"은 없앴다.) LIKE를 못 하는 사람은 같은 등급 안에서 뒤로 보낸다
    # → api/v1/matching.discover, membership_service.cannot_like_ids. members_only는 예전 호출 호환용(무시).
    return query


def is_vip_tester(user: User) -> bool:
    """예전 이름 호환용. VIP 판단은 vip_service에 있다."""
    return vip_service.is_vip_tester(user)


def _pass_cutoff(hours: int | None = None) -> datetime:
    """이 시각 이후에 PASS한 사람은 아직 추천에서 뺀다 (PASS 후 hours 동안, 기본 48시간·VIP 24시간)."""
    return utcnow() - timedelta(hours=hours if hours is not None else get_settings().pass_cooldown_hours)


# 서버가 켜진 시각 (= VIP "그날만 숨김" 규칙을 처음 배포한 시각, 2026-10-02).
# 이보다 먼저 VIP를 PASS한 기록은 무시한다 → 배포하자마자 모두에게 다시 추천된다.
VIP_PASS_RESET_FROM = utcnow()


def _pass_still_hides(to_id: uuid.UUID, passed_at, vip_ids: set[uuid.UUID], cutoff: datetime) -> bool:
    """이 PASS가 아직 상대를 추천에서 숨기는가?

    - VIP에게 한 PASS: 그날 하루(한국 시간 자정까지)만 (VIP 혜택 5)
    - 그 밖: PASS한 사람(나)의 규칙대로 — 무료 48시간, 내가 VIP면 24시간 (VIP 혜택 2)
    """
    if passed_at is None:
        return False
    passed_at = as_utc(passed_at)
    if to_id in vip_ids:
        return passed_at >= max(kst_day_start(), VIP_PASS_RESET_FROM)
    return passed_at > cutoff


def _passes(db: Session, user_id: uuid.UUID):
    return db.query(Like.to_user_id, Like.updated_at).filter(Like.from_user_id == user_id, Like.action == "PASS")


def excluded_user_ids(
    db: Session, user_id: uuid.UUID, *, pass_cooldown_hours: int | None = None, include_passed: bool = True
) -> set[uuid.UUID]:
    """추천에서 빼야 할 사람: 최근에 LIKE한 사람, 최근에 PASS한 사람, 차단 관계(양방향), 매칭 이력이 있는 사람.

    LIKE (2026-10-24 재설계): 예전에는 한 번 LIKE한 사람은 영원히 뺐다. 지금은 마지막 LIKE 후
    LIKE_REPEAT_HOURS(48시간) 동안만 빼고, 그때까지 매칭이 안 됐으면 다시 나온다 (다시 LIKE 가능 → 횟수가 쌓임).

    PASS는 영원히 빼지 않는다 (2026-10-02). 베타라 사람이 적어서 추천이 금방 바닥나기 때문.
    - 보통: PASS 후 48시간 동안만 뺀다. 내가 VIP면 24시간 (pass_cooldown_hours로 받음)
    - VIP를 PASS한 경우: 그날 하루만 뺀다 → 매일 다시 추천된다
    PASS 시각은 updated_at으로 본다 (같은 사람을 다시 PASS하면 그때 시각으로 바뀐다 → _upsert_action).
    include_passed=False: PASS는 따지지 않는다 (VIP "받은 LIKE" 목록 — PASS한 사람도 보여줌).
    """
    ids: set[uuid.UUID] = {user_id}
    like_cutoff = utcnow() - timedelta(hours=get_settings().like_repeat_hours)
    ids.update(
        r[0]
        for r in db.query(Like.to_user_id).filter(
            Like.from_user_id == user_id, Like.action == "LIKE", Like.created_at > like_cutoff
        )
    )
    if include_passed:
        vip_ids = vip_service.vip_user_ids(db)
        cutoff = _pass_cutoff(pass_cooldown_hours)
        ids.update(to_id for to_id, at in _passes(db, user_id) if _pass_still_hides(to_id, at, vip_ids, cutoff))
    ids.update(r[0] for r in db.query(Block.blocked_user_id).filter(Block.blocker_user_id == user_id))
    ids.update(r[0] for r in db.query(Block.blocker_user_id).filter(Block.blocked_user_id == user_id))
    for a, b in db.query(Match.user_a_id, Match.user_b_id).filter((Match.user_a_id == user_id) | (Match.user_b_id == user_id)):
        ids.update((a, b))
    return ids


def passed_before_ids(db: Session, user_id: uuid.UUID, *, pass_cooldown_hours: int | None = None) -> set[uuid.UUID]:
    """예전에 PASS했지만 이제 다시 추천될 수 있는 사람. 추천 순서에서 "처음 보는 사람" 뒤로 보낸다."""
    vip_ids = vip_service.vip_user_ids(db)
    cutoff = _pass_cutoff(pass_cooldown_hours)
    return {to_id for to_id, at in _passes(db, user_id) if not _pass_still_hides(to_id, at, vip_ids, cutoff)}


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
        tier_same=s.rec_tier_same,
        tier_one=s.rec_tier_one,
        tier_two=s.rec_tier_two,
        activity_max=s.rec_activity_max,
        liked_max=s.rec_liked_max,
        liked_full=s.rec_liked_full,
        taste_max=s.rec_taste_max,
        effort_max=s.rec_effort_max,
    )


def current_tier(db: Session, user_id: uuid.UUID) -> str | None:
    """가장 최근 외모 평가의 등급 (내부 전용 — API 응답에 넣지 말 것)."""
    evaluation = latest_evaluations(db, [user_id]).get(user_id)
    return evaluation.tier if evaluation else None


def liked_me_ids(db: Session, user_id: uuid.UUID) -> set[uuid.UUID]:
    """추천 우대용: 나에게 LIKE를 보낸 사람들. 사용자에게는 절대 알려주지 않는다.

    VIP는 하루 LIKE가 10개지만, 우대는 보낸 사람의 그날(한국 시간) 처음 LIKER_BOOST_LIMIT(5)개에만 준다.
    6~10번째 LIKE는 우대 없는 일반 LIKE다 (상대도 LIKE하면 매칭은 된다).
    """
    senders = {r[0] for r in db.query(Like.from_user_id).filter(Like.to_user_id == user_id, Like.action == "LIKE")}
    if not senders:
        return set()
    limit = get_settings().liker_boost_limit
    rows = (
        db.query(Like.from_user_id, Like.to_user_id, Like.created_at)
        .filter(Like.from_user_id.in_(senders), Like.action == "LIKE")
        .order_by(Like.created_at, Like.id)
        .all()
    )
    rank: dict[tuple, int] = defaultdict(int)
    boosted: set[uuid.UUID] = set()
    for sender, target, created in rows:
        day = kst_today(as_utc(created))
        rank[(sender, day)] += 1
        if target == user_id and rank[(sender, day)] <= limit:
            boosted.add(sender)
    return boosted


def liked_counts(db: Session, user_id: uuid.UUID) -> dict[uuid.UUID, int]:
    """나에게 좋아요를 보낸 사람 → 보낸 횟수 (2026-10-24 가중치 ③). 사용자에게는 절대 알려주지 않는다 (VIP 받은 LIKE 목록 제외)."""
    return dict(
        db.query(Like.from_user_id, Like.like_count).filter(Like.to_user_id == user_id, Like.action == "LIKE").all()
    )


def sent_like_counts(db: Session, user_id: uuid.UUID, to_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    """내가 보낸 좋아요 횟수 (2026-10-24). 넘기기로 바뀐 행도 쌓인 횟수는 남아 있다."""
    if not to_ids:
        return {}
    return dict(
        db.query(Like.to_user_id, Like.like_count)
        .filter(Like.from_user_id == user_id, Like.to_user_id.in_(to_ids), Like.like_count > 0)
        .all()
    )


def likers_of(db: Session, user_id: uuid.UUID) -> list[tuple[uuid.UUID, datetime]]:
    """나를 LIKE한 사람과 그 시각, 최근 순 (VIP "받은 LIKE" 목록용, 우대 제한과 상관없이 전부)."""
    return [
        (uid, at)
        for uid, at in db.query(Like.from_user_id, Like.created_at)
        .filter(Like.to_user_id == user_id, Like.action == "LIKE")
        .order_by(Like.created_at.desc())
        .all()
    ]


def likes_sent_today(db: Session, user_id: uuid.UUID) -> int:
    """오늘(한국 시간 0시 이후) 보낸 LIKE 수.

    LIKE는 항상 새 행으로 생긴다 (이미 LIKE한 상대에게는 다시 LIKE할 수 없음 → excluded_user_ids).
    PASS 48시간이 지나 다시 나온 사람에게 LIKE하면, PASS 행을 지우고 새 행을 만든다 (_upsert_action).
    PASS를 취소해도 행이 지워진다. 그래서 created_at으로 셀 수 있다.
    """
    return (
        db.query(func.count(Like.id))
        .filter(
            Like.from_user_id == user_id,
            Like.action == "LIKE",
            Like.is_trial.is_(False),  # 체험 LIKE는 하루 한도에서 뺀다 (2026-10-06)
            Like.is_super.is_(False),  # 슈퍼 라이크도 따로 센다 (2026-10-12)
            Like.created_at >= kst_day_start(),
        )
        .scalar()
        or 0
    )


def likes_left_today(db: Session, user_id: uuid.UUID, limit: int | None = None) -> int:
    """오늘 남은 LIKE 수. limit: 하루 한도 (무료 5개, VIP 10개 → vip_service.daily_like_limit)."""
    if limit is None:
        limit = get_settings().daily_like_limit
    return max(0, limit - likes_sent_today(db, user_id))


def count(db: Session, query) -> int:
    return db.query(func.count()).select_from(query.subquery()).scalar() or 0
