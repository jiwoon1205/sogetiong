"""/api/v1/admin/popups — 공지 팝업 진행 상황 · 켜기/끄기 (2026-11-24).

- 친구 초대 이벤트 팝업 (매일): 오늘 본 사람, 평생 VIP 달성자, 초대 진행 분포 · 상위 사람
- 앱 설치 안내 팝업 (3일에 한 번): 최근 3일·전체 본 사람, 앱으로 쓰는 사람
- 찬반 투표(설문)는 관리자 → 설문 화면 (여기서는 요약과 바로가기만)
보기: dashboard:read · 켜기/끄기: surveys:manage (감사 로그 POPUP_ON / POPUP_OFF)
"""

from collections import Counter
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.time import KST, as_utc, kst_today, utcnow
from app.db.session import get_db
from app.deps import CurrentAdmin, require_permission
from app.models.profile import PublicProfile
from app.models.survey import SurveyResponse
from app.models.university import University
from app.models.user import User, UserDailyVisit
from app.services import (
    announcement_service,
    audit_service,
    khu_vip_service,
    popup_service,
    profile_service,
    survey_service,
)

router = APIRouter()


class PopupToggle(BaseModel):
    enabled: bool


def _active_week(db: Session):
    """활성 사용자 (사진 검수 완료 + 최근 7일 접속) id 쿼리"""
    week_start = kst_today() - timedelta(days=6)
    visitors = db.query(UserDailyVisit.user_id).filter(UserDailyVisit.visit_date >= week_start)
    return (
        db.query(User.id)
        .filter(User.status == "ACTIVE", User.id.in_(visitors))
        .filter(User.id.in_(profile_service.approved_photo_user_ids(db)))
    )


def _invite_progress(db: Session) -> dict:
    """평생 VIP 초대 이벤트: 사람별 인정된 초대 수 (경희대생은 11-22부터, 나머지는 11-24부터)."""
    earliest = min(khu_vip_service.KHU_START, khu_vip_service.START)
    rows = (
        db.query(User.referred_by_id, User.created_at)
        .filter(User.referred_by_id.isnot(None), User.referral_rewarded_at.isnot(None), User.created_at >= earliest)
        .all()
    )
    referrer_ids = {r for r, _ in rows}
    khu_ids = {u for (u,) in db.query(University.id).filter(University.email_domain == khu_vip_service.DOMAIN)}
    referrers = {u.id: u for u in db.query(User).filter(User.id.in_(referrer_ids))} if referrer_ids else {}
    counts: Counter = Counter()
    for ref_id, created in rows:
        ref = referrers.get(ref_id)
        if ref is None:
            continue
        start = khu_vip_service.KHU_START if ref.university_id in khu_ids else khu_vip_service.START
        if as_utc(created) >= as_utc(start):
            counts[ref_id] += 1
    goal = khu_vip_service.GOAL
    nick = dict(db.query(PublicProfile.user_id, PublicProfile.nickname).filter(PublicProfile.user_id.in_(list(counts))).all()) if counts else {}
    uni = dict(db.query(University.id, University.name).all())
    top = [
        {
            "user_id": str(uid),
            "nickname": nick.get(uid),
            "school": uni.get(referrers[uid].university_id),
            "count": min(n, goal),
            "done": khu_vip_service.has_lifetime(referrers[uid]),
        }
        for uid, n in counts.most_common(10)
    ]
    return {
        "inviters": len(counts),
        "half_way": sum(1 for n in counts.values() if n >= goal // 2),
        "top": top,
    }


@router.get("/popups")
def popups(admin: CurrentAdmin = Depends(require_permission("dashboard:read")), db: Session = Depends(get_db)):
    today_key = announcement_service.khu_vip_key()
    lifetime = db.query(func.count(User.id)).filter(User.vip_until >= datetime(2999, 1, 1, tzinfo=KST)).scalar() or 0
    active = _active_week(db)
    active_n = active.count()
    now = utcnow()
    app_users = db.query(func.count(User.id)).filter(User.id.in_(active), User.app_opened_at.isnot(None)).scalar() or 0
    survey_votes = (
        db.query(func.count(SurveyResponse.id)).filter(SurveyResponse.survey_key == survey_service.SURVEY_KEY).scalar() or 0
    )
    return {
        "order": "찬반 투표 → (공지) 친구 초대 이벤트 → 다음 접속에 앱 설치 안내 순서로, 한 번에 하나만 떠요.",
        "survey": {"open": survey_service.is_open(db), "votes": survey_votes, "key": survey_service.SURVEY_KEY},
        "invite": {
            "enabled": popup_service.enabled(db, "invite"),
            "schedule": "매일 한 번 (가입한 날은 빼고) · 평생 VIP가 된 사람에게는 안 뜸",
            "goal": khu_vip_service.GOAL,
            "seen_today": db.query(func.count(User.id)).filter(User.announcement_seen == today_key).scalar() or 0,
            "lifetime_vip": lifetime,
            "active_users": active_n,
            **_invite_progress(db),
        },
        "install": {
            "enabled": popup_service.enabled(db, "install"),
            "schedule": f"{3}일에 한 번 · 브라우저로 들어온 사람에게만 · 그 접속에 다른 팝업이 없을 때만",
            "seen_3days": db.query(func.count(User.id)).filter(User.install_popup_seen_at >= now - timedelta(days=3)).scalar() or 0,
            "seen_total": db.query(func.count(User.id)).filter(User.install_popup_seen_at.isnot(None)).scalar() or 0,
            "app_users": app_users,
            "active_users": active_n,
        },
    }


@router.put("/popups/{name}")
def toggle(
    name: str,
    payload: PopupToggle,
    request: Request,
    admin: CurrentAdmin = Depends(require_permission("surveys:manage")),
    db: Session = Depends(get_db),
):
    if name not in popup_service.POPUPS:
        raise HTTPException(status_code=404, detail="없는 팝업이에요.")
    popup_service.set_enabled(db, name, payload.enabled)
    audit_service.record(
        db,
        admin_id=admin.id,
        action="POPUP_ON" if payload.enabled else "POPUP_OFF",
        target_type="POPUP",
        target_id=None,
        request=request,
        metadata={"popup": name},
    )
    db.commit()
    return {"name": name, "enabled": payload.enabled}
