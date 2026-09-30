"""/api/v1 — 차단, 신고, 알림."""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.rate_limit import enforce_rate_limit
from app.core.time import utcnow
from app.db.session import get_db
from app.deps import CurrentUser, get_current_user
from app.models.matching import Block, Match, Notification, Report
from app.models.profile import PublicProfile
from app.schemas.matching import NotificationUpdateRequest, ReportRequest, TargetRequest
from app.services import admin_alert_service, profile_service
from app.services.email_service import EmailService

router = APIRouter()


def _target_user_id(db: Session, current: CurrentUser, profile_id: uuid.UUID) -> uuid.UUID:
    """차단·신고는 정지된 사용자에게도 할 수 있어야 하므로 계정 상태는 따지지 않는다."""
    profile = db.get(PublicProfile, profile_id)
    if profile is None or profile.user_id == current.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="프로필을 찾을 수 없습니다.")
    return profile.user_id


# ---------- 차단 (설계도 §26) ----------

@router.post("/blocks", status_code=status.HTTP_201_CREATED)
def block(payload: TargetRequest, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    enforce_rate_limit(f"block:{current.id}", 30, 3600)
    target = _target_user_id(db, current, payload.profile_id)
    exists = db.query(Block.id).filter(Block.blocker_user_id == current.id, Block.blocked_user_id == target).first()
    if not exists:
        db.add(Block(blocker_user_id=current.id, blocked_user_id=target))
    # 진행 중인 매칭/채팅 종료. 상대에게 차단 사실을 알리지 않는다.
    a, b = profile_service.match_pair(current.id, target)
    db.query(Match).filter(Match.user_a_id == a, Match.user_b_id == b, Match.status == "ACTIVE").update(
        {"status": "BLOCKED", "ended_at": utcnow()}, synchronize_session=False
    )
    db.commit()
    return {"blocked": True}


@router.get("/blocks")
def list_blocks(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(Block, PublicProfile)
        .outerjoin(PublicProfile, PublicProfile.user_id == Block.blocked_user_id)
        .filter(Block.blocker_user_id == current.id)
        .order_by(Block.created_at.desc())
        .all()
    )
    return {
        "blocks": [
            {
                "profile_id": str(profile.id) if profile else None,
                "nickname": profile.nickname if profile else "탈퇴한 사용자",
                "blocked_at": blk.created_at.isoformat(),
            }
            for blk, profile in rows
        ]
    }


@router.delete("/blocks/{profile_id}")
def unblock(profile_id: uuid.UUID, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """차단 해제. 끝난 매칭은 되살리지 않고, 다시 추천되지도 않는다 (재매칭 방지)."""
    target = _target_user_id(db, current, profile_id)
    deleted = db.query(Block).filter(Block.blocker_user_id == current.id, Block.blocked_user_id == target).delete(
        synchronize_session=False
    )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="차단 기록이 없습니다.")
    db.commit()
    return {"unblocked": True}


# ---------- 신고 (설계도 §27) ----------

@router.post("/reports", status_code=status.HTTP_201_CREATED)
def report(
    payload: ReportRequest,
    background: BackgroundTasks,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enforce_rate_limit(f"report:{current.id}", 5, 3600)
    if payload.match_id:
        # 대화방 기준 신고: 대화가 끝났거나 상대가 탈퇴·정지돼도 신고할 수 있다 (상대 공개 프로필이 없어도 됨)
        match = db.get(Match, payload.match_id)
        if match is None or not match.has_member(current.id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="대화방 정보가 올바르지 않습니다.")
        target = match.partner_of(current.id)
        if payload.profile_id and _target_user_id(db, current, payload.profile_id) != target:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="대화방 정보가 올바르지 않습니다.")
    else:
        target = _target_user_id(db, current, payload.profile_id)
    open_report = (
        db.query(Report.id)
        .filter(
            Report.reporter_user_id == current.id,
            Report.reported_user_id == target,
            Report.status.in_(["OPEN", "IN_REVIEW"]),
        )
        .first()
    )
    if open_report:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 처리 중인 신고가 있습니다.")
    row = Report(
        reporter_user_id=current.id,
        reported_user_id=target,
        match_id=payload.match_id,
        reason=payload.reason,
        description=payload.description.strip() if payload.description else None,
    )
    db.add(row)
    db.commit()

    # 신고 담당 운영진에게 바로 메일 (응답을 보낸 뒤 발송). 메일에는 사유와 관리자 화면 링크만 넣는다.
    recipients = admin_alert_service.admin_emails_with(db, "reports:update")
    background.add_task(admin_alert_service.send_all, EmailService.send_admin_new_report, recipients, payload.reason)
    return {"report_id": str(row.id), "status": row.status}


# ---------- 알림 (설계도 §58) ----------

@router.get("/notifications")
def list_notifications(
    unread_only: bool = False, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)
):
    query = db.query(Notification).filter(Notification.user_id == current.id)
    if unread_only:
        query = query.filter(Notification.read_at.is_(None))
    rows = query.order_by(Notification.created_at.desc()).limit(50).all()
    return {
        "notifications": [
            {
                "notification_id": str(n.id),
                "type": n.type,
                "title": n.title,
                "body": n.body,
                "related_id": str(n.related_id) if n.related_id else None,
                "read": n.read_at is not None,
                "created_at": n.created_at.isoformat(),
            }
            for n in rows
        ]
    }


@router.patch("/notifications/{notification_id}")
def update_notification(
    notification_id: uuid.UUID,
    payload: NotificationUpdateRequest,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != current.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="알림을 찾을 수 없습니다.")
    n.read_at = utcnow() if payload.read else None
    db.commit()
    return {"notification_id": str(n.id), "read": payload.read}
