"""이탈 막기 (2026-11-16, `거절이 쌓인 남성 돕기·휴면 좋아요 알림 (2026-11-16)`).

근거: `사용자 이탈 분석 (2026-11-16)`
- 받은 반응 중 넘기기가 95% 넘는 남성은 81%가 휴면. 자기소개 30자 넘으면 휴면 가능성 38% 낮음.
- 휴면 423명 중 매칭 경험 182명 → 다시 데려올 수 있는 사람이 많다.

1) 매칭 확률 높이기 안내 (팝업 한 번)
   남성, 사진 승인됨, 접속한 날 3일 이상, 매칭 0회 → 한 번만 팝업. 닫으면 알림 목록에도 남긴다.
   내 프로필 기준 맞춤 점검(자기소개 글자 수·관심사·MBTI) + 인스타 감성 사진 안내.
2) 휴면 계정 좋아요 알림
   마지막 접속이 7일 넘게 지난 사람이 좋아요를 받으면 휴대폰 알림, 알림을 안 켰으면 학교 메일.
   한 사람에게 3일에 최대 1번. 누가 보냈는지는 알려주지 않는다.
"""

from datetime import timedelta

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.time import as_utc, utcnow
from app.models.matching import Match
from app.models.profile import UserInterest
from app.models.user import User, UserDailyVisit
from app.services import profile_service, push_service, vip_service
from app.services.notification_service import notify

TIP_NOTICE = "MATCH_TIP"  # 알림 종류 (누르면 프로필 화면)
GOOD_BIO = 100  # 자기소개 이만큼 쓰면 "충분"
GOOD_INTERESTS = 4


def _profile_check(user: User, db: Session) -> dict:
    profile = getattr(user, "public_profile", None)
    bio = len((profile.bio or "").strip()) if profile else 0
    interests = db.query(UserInterest).filter(UserInterest.user_id == user.id).count()
    return {
        "bio_chars": bio,
        "bio_good": bio >= GOOD_BIO,
        "interests": interests,
        "interests_good": interests >= GOOD_INTERESTS,
        "mbti_set": bool(profile and profile.mbti),
        "good_bio_chars": GOOD_BIO,
        "good_interests": GOOD_INTERESTS,
    }


def match_tip(db: Session, user: User) -> dict | None:
    """팝업을 보여줄 차례면 맞춤 점검 내용, 아니면 None."""
    s = get_settings()
    if s.match_tip_min_visit_days <= 0 or user.match_tip_seen_at is not None:
        return None
    if vip_service.gender_of(user) != "MALE" or vip_service.is_vip_tester(user) or user.super_vip:
        return None
    if not profile_service.has_approved_photo(db, user.id):
        return None
    visits = db.query(UserDailyVisit).filter(UserDailyVisit.user_id == user.id).count()
    if visits < s.match_tip_min_visit_days:
        return None
    matched = db.query(Match.id).filter(or_(Match.user_a_id == user.id, Match.user_b_id == user.id)).first()
    if matched is not None:
        return None
    return _profile_check(user, db)


def mark_match_tip_seen(db: Session, user: User) -> None:
    """팝업을 닫음 → 다시 띄우지 않고, 알림 목록에 같은 내용을 남긴다 (나중에 다시 볼 수 있게)."""
    if user.match_tip_seen_at is not None:
        return
    user.match_tip_seen_at = utcnow()
    notify(
        db,
        user.id,
        TIP_NOTICE,
        "매칭 확률을 높이는 방법",
        f"자기소개를 {GOOD_BIO}자 넘게 쓰고 관심사·MBTI를 채운 사람이 매칭이 훨씬 많았어요. "
        "사진은 인스타에 올릴 법한 자연스러운 분위기의 사진이 평가가 잘 나와요.",
    )


def maybe_winback(db: Session, target_id, now=None) -> bool:
    """좋아요를 받은 사람이 휴면이면 알림을 보낸다 (3일에 최대 1번). 보냈으면 True. commit은 부르는 쪽에서."""
    s = get_settings()
    if s.winback_dormant_days <= 0:
        return False
    now = now or utcnow()
    user = db.get(User, target_id)
    if user is None or user.status != "ACTIVE" or user.deleted_at is not None:
        return False
    last = as_utc(user.last_active_at)
    if last is None or now - last < timedelta(days=s.winback_dormant_days):
        return False
    sent = as_utc(user.winback_sent_at)
    if sent is not None and now - sent < timedelta(days=s.winback_interval_days):
        return False
    user.winback_sent_at = now
    push_service.queue(db, user.id, push_service.LIKED, None)
    return True
