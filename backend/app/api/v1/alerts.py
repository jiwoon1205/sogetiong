"""/api/v1/me/alerts — 휴대폰 알림(웹 푸시) 켜기·끄기, 메일 알림 설정 (2026-10-05).

규칙은 app/services/push_service.py 맨 위 설명.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.rate_limit import enforce_rate_limit
from app.db.session import get_db
from app.deps import CurrentUser, get_current_user
from app.models.push import PushSubscription
from app.schemas.alerts import AlertSettingsRequest, AnnouncementSeenRequest, PushSubscribeRequest, PushUnsubscribeRequest
from app.services import announcement_service, push_service

router = APIRouter()


def _state(db: Session, current: CurrentUser) -> dict:
    settings = get_settings()
    devices = db.query(PushSubscription).filter(PushSubscription.user_id == current.id).count()
    return {
        # 서버에 VAPID 열쇠가 들어 있어 휴대폰 알림을 쓸 수 있는가
        "push_available": settings.push_enabled,
        # 브라우저가 알림 주소를 만들 때 쓰는 공개 열쇠 (비밀 아님)
        "public_key": settings.vapid_public_key.strip() if settings.push_enabled else None,
        # 알림을 켠 기기 수 (이 기기 포함 여부는 화면이 브라우저에 직접 확인한다)
        "device_count": devices,
        "email_notify": current.user.email_notify,
    }


@router.get("/me/alerts")
def get_alerts(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return _state(db, current)


@router.patch("/me/alerts")
def update_alerts(
    payload: AlertSettingsRequest, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)
):
    current.user.email_notify = payload.email_notify
    db.commit()
    return _state(db, current)


@router.put("/me/alerts/push")
def subscribe_push(
    payload: PushSubscribeRequest,
    request: Request,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """이 기기(브라우저)에서 알림 켜기. 화면이 열릴 때마다 다시 불러도 된다 (지금 로그인한 세션에 다시 묶음)."""
    settings = get_settings()
    if not settings.push_enabled:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="휴대폰 알림은 아직 준비 중이에요.")
    enforce_rate_limit(f"push-sub:{current.id}", 20, 60)

    sub = db.query(PushSubscription).filter(PushSubscription.endpoint == payload.endpoint).first()
    if sub is None:
        sub = PushSubscription(endpoint=payload.endpoint)
        db.add(sub)
    # 같은 브라우저에서 다른 계정으로 로그인했던 경우에도 지금 로그인한 사람·세션으로 옮긴다
    sub.user_id = current.id
    sub.session_id = current.session.id
    sub.p256dh = payload.keys.p256dh
    sub.auth = payload.keys.auth
    sub.user_agent = (request.headers.get("user-agent") or "")[:300] or None
    db.flush()

    # 기기가 너무 많으면 가장 오래된 것부터 지운다
    rows = (
        db.query(PushSubscription)
        .filter(PushSubscription.user_id == current.id)
        .order_by(PushSubscription.created_at.desc())
        .all()
    )
    for old in rows[settings.push_max_devices :]:
        if old.id != sub.id:
            db.delete(old)
    db.commit()
    return {**_state(db, current), "subscribed": True}


@router.delete("/me/alerts/push")
def unsubscribe_push(
    payload: PushUnsubscribeRequest, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)
):
    db.query(PushSubscription).filter(
        PushSubscription.user_id == current.id, PushSubscription.endpoint == payload.endpoint
    ).delete(synchronize_session=False)
    db.commit()
    return {**_state(db, current), "subscribed": False}


@router.post("/me/alerts/push/test")
def test_push(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """"테스트 알림 보내기" 버튼: 이 기기로 알림 한 통 (10분 제한·화면 보는 중 규칙 없이 바로)."""
    if not get_settings().push_enabled:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="휴대폰 알림은 아직 준비 중이에요.")
    enforce_rate_limit(f"push-test:{current.id}", 5, 60)
    subs = db.query(PushSubscription).filter(PushSubscription.session_id == current.session.id).all()
    if not subs:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이 기기에서 알림이 켜져 있지 않아요.")
    delivered = push_service.send_to_devices(
        db, subs, {"title": "훕팅", "body": "알림이 잘 켜졌어요", "url": "/settings#alerts", "tag": "test"}
    )
    if delivered == 0:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="알림을 보내지 못했어요. 알림을 껐다가 다시 켜 보세요.",
        )
    return {"delivered": delivered}


@router.post("/me/alerts/away")
def mark_away(current: CurrentUser = Depends(get_current_user)):
    """대화방 화면을 닫거나 다른 앱으로 갔을 때 화면이 부른다 (2026-10-06).
    이때부터 새 메시지가 오면 바로 휴대폰 알림이 간다 (12초를 기다리지 않음)."""
    push_service.mark_away(current.id)
    return {"ok": True}


# ---------- 한 번만 보여주는 공지 팝업 (2026-10-05) ----------

@router.post("/me/announcement/seen")
def mark_announcement_seen(
    payload: AnnouncementSeenRequest, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)
):
    """공지 팝업에서 "확인"(또는 버튼)을 누름 → 이 계정에는 다시 안 뜬다 (하루 공지는 오늘만 안 뜸)."""
    if not announcement_service.is_showable(current.user, payload.key):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="지금 보여주는 공지가 아니에요.")
    current.user.announcement_seen = payload.key
    db.commit()
    return {"announcement": None}
