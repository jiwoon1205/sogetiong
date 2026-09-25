"""/api/v1/admin — 관리자 전용. 모든 API는 로그인 + 2단계 인증 + 권한(RBAC)을 확인한다."""

import uuid
from io import BytesIO

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.rate_limit import client_ip, enforce_rate_limit
from app.core.security import pseudonymous_code, verify_password
from app.core.time import utcnow
from app.db.session import get_db
from app.deps import CurrentAdmin, get_admin_pending_mfa, get_current_admin, require_permission
from app.models.admin import AdminUser, AuditLog
from app.models.matching import Match, Report
from app.models.photo import AppearanceEvaluation, UserPhoto
from app.models.profile import PrivateProfile, PublicProfile
from app.models.user import User
from app.schemas.admin import (
    AdminLoginRequest,
    AdminTwoFactorRequest,
    EvaluationRequest,
    ReportUpdateRequest,
    UserStatusRequest,
)
from app.services import profile_service
from app.services.audit_service import AuditService
from app.services.notification_service import notify
from app.services.session_service import (
    clear_admin_cookies,
    create_admin_session,
    revoke_all_user_sessions,
    set_admin_cookies,
)
from app.services.storage_service import get_storage

router = APIRouter()


# ---------- 관리자 로그인 (비밀번호 → 2단계 인증) ----------

@router.post("/auth/login")
def admin_login(payload: AdminLoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    enforce_rate_limit(f"admin-login:ip:{client_ip(request)}", 10, 900)
    admin = db.query(AdminUser).filter(AdminUser.email == payload.email.lower()).first()
    if not verify_password(payload.password, admin.password_hash if admin else None) or admin.status != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="이메일 또는 비밀번호가 올바르지 않습니다.")
    if not admin.totp_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="2단계 인증이 설정되지 않은 계정입니다.")
    issued = create_admin_session(db, admin.id, request)
    db.commit()
    set_admin_cookies(response, issued)
    return {"mfa_required": True, "csrf_token": issued.csrf_token}


@router.post("/auth/2fa")
def admin_two_factor(
    payload: AdminTwoFactorRequest,
    request: Request,
    admin: CurrentAdmin = Depends(get_admin_pending_mfa),
    db: Session = Depends(get_db),
):
    enforce_rate_limit(f"admin-2fa:{admin.id}", 5, 300)
    if not pyotp.TOTP(admin.admin.totp_secret).verify(payload.code, valid_window=1):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="인증 코드가 올바르지 않습니다.")
    now = utcnow()
    admin.session.mfa_verified_at = now
    admin.admin.last_login_at = now
    AuditService.record(db, admin_id=admin.id, action="ADMIN_LOGIN", target_type="ADMIN", target_id=admin.id, request=request)
    db.commit()
    return {"role": admin.role, "permissions": sorted(admin.permissions)}


@router.post("/auth/logout")
def admin_logout(response: Response, admin: CurrentAdmin = Depends(get_admin_pending_mfa), db: Session = Depends(get_db)):
    db.delete(admin.session)
    db.commit()
    clear_admin_cookies(response)
    return {"message": "로그아웃되었습니다."}


@router.get("/me")
def admin_me(admin: CurrentAdmin = Depends(get_current_admin)):
    return {"email": admin.admin.email, "role": admin.role, "permissions": sorted(admin.permissions)}


# ---------- 대시보드 (개인정보 없이 숫자만, 설계도 §59) ----------

@router.get("/dashboard")
def dashboard(admin: CurrentAdmin = Depends(require_permission("dashboard:read")), db: Session = Depends(get_db)):
    def c(q):
        return profile_service.count(db, q)

    return {
        "users_total": c(db.query(User.id)),
        "users_active": c(db.query(User.id).filter(User.status == "ACTIVE")),
        "users_suspended": c(db.query(User.id).filter(User.status.in_(["SUSPENDED", "BANNED"]))),
        "photos_pending": c(db.query(UserPhoto.id).filter(UserPhoto.review_status.in_(["PENDING", "IN_REVIEW"]))),
        "matches_total": c(db.query(Match.id)),
        "reports_open": c(db.query(Report.id).filter(Report.status.in_(["OPEN", "IN_REVIEW"]))),
    }


# ---------- 사진 검수 / 외적 평가 ----------
# PHOTO_REVIEWER는 사진과 가명 코드(U1A2B3C)만 본다. 이름·이메일·학번 등은 보이지 않는다 (설계도 §29).

def _photo_or_404(db: Session, photo_id: uuid.UUID) -> UserPhoto:
    photo = db.get(UserPhoto, photo_id)
    if photo is None or photo.upload_status == "DELETED":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="사진을 찾을 수 없습니다.")
    return photo


def _photo_summary(photo: UserPhoto) -> dict:
    return {
        "photo_id": str(photo.id),
        "subject_code": pseudonymous_code(photo.user_id),
        "review_status": photo.review_status,
        "uploaded_at": photo.uploaded_at.isoformat(),
        "reviewed_at": photo.reviewed_at.isoformat() if photo.reviewed_at else None,
    }


@router.get("/photo-reviews")
def list_photo_reviews(
    status_filter: str = Query(default="PENDING", alias="status", pattern="^(PENDING|IN_REVIEW|APPROVED|REJECTED)$"),
    admin: CurrentAdmin = Depends(require_permission("photos:read")),
    db: Session = Depends(get_db),
):
    photos = (
        db.query(UserPhoto)
        .filter(UserPhoto.review_status == status_filter, UserPhoto.upload_status != "DELETED")
        .order_by(UserPhoto.uploaded_at.asc())
        .limit(100)
        .all()
    )
    return {"photos": [_photo_summary(p) for p in photos]}


@router.get("/photo-reviews/{photo_id}")
def get_photo_review(
    photo_id: uuid.UUID,
    admin: CurrentAdmin = Depends(require_permission("photos:read")),
    db: Session = Depends(get_db),
):
    photo = _photo_or_404(db, photo_id)
    if photo.review_status == "PENDING":
        photo.review_status = "IN_REVIEW"
        db.commit()
    history = (
        db.query(AppearanceEvaluation)
        .filter(AppearanceEvaluation.user_id == photo.user_id)
        .order_by(AppearanceEvaluation.created_at.desc())
        .limit(5)
        .all()
    )
    return {
        **_photo_summary(photo),
        "image_url": f"/api/v1/admin/photo-reviews/{photo.id}/image",
        "evaluation_history": [{**e.scores(), "note": e.evaluation_note, "created_at": e.created_at.isoformat()} for e in history],
    }


def _watermark(data: bytes, text: str) -> bytes:
    """관리자 이메일+시각을 사진에 새겨서, 화면 캡처가 유출되면 누가 봤는지 알 수 있게 한다 (설계도 §39)."""
    with Image.open(BytesIO(data)) as image:
        image = image.convert("RGB")
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default(size=max(14, image.width // 28))
        step = max(image.height // 6, 40)
        for y in range(10, image.height, step):
            draw.text((13, y + 2), text, fill=(0, 0, 0), font=font)
            draw.text((12, y), text, fill=(255, 255, 255), font=font)
        out = BytesIO()
        image.save(out, format="JPEG", quality=85)
        return out.getvalue()


@router.get("/photo-reviews/{photo_id}/image")
def get_photo_image(
    photo_id: uuid.UUID,
    request: Request,
    admin: CurrentAdmin = Depends(require_permission("photos:read")),
    db: Session = Depends(get_db),
):
    """서버 프록시 방식. 영구 URL을 만들지 않고, 캐시·다운로드를 막는 헤더를 붙인다."""
    photo = _photo_or_404(db, photo_id)
    try:
        data = get_storage().read(photo.storage_key)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="사진 파일이 없습니다.") from exc
    AuditService.record(db, admin_id=admin.id, action="PHOTO_VIEW", target_type="USER_PHOTO", target_id=photo.id, request=request)
    db.commit()
    stamped = _watermark(data, f"{admin.admin.email} {utcnow():%Y-%m-%d %H:%M}")
    return Response(
        content=stamped,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store, private", "Content-Disposition": "inline", "X-Content-Type-Options": "nosniff"},
    )


@router.put("/photo-reviews/{photo_id}/evaluation")
def evaluate_photo(
    photo_id: uuid.UUID,
    payload: EvaluationRequest,
    request: Request,
    admin: CurrentAdmin = Depends(require_permission("photos:evaluate")),
    db: Session = Depends(get_db),
):
    photo = _photo_or_404(db, photo_id)
    if photo.review_status == "SUPERSEDED":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="새 사진으로 대체된 사진입니다.")

    previous = profile_service.latest_evaluations(db, [photo.user_id]).get(photo.user_id)
    before = previous.scores() if previous else None
    now = utcnow()
    photo.reviewed_at = now
    photo.reviewed_by = admin.id

    if payload.decision == "APPROVED":
        photo.review_status = "APPROVED"
        photo.reject_reason = None
        evaluation = AppearanceEvaluation(
            user_id=photo.user_id,
            photo_id=photo.id,
            overall_impression=payload.overall_impression,
            style=payload.style,
            grooming=payload.grooming,
            photo_vibe=payload.photo_vibe,
            evaluator_admin_id=admin.id,
            evaluation_note=payload.note,
        )
        db.add(evaluation)
        after = evaluation.scores()
        action = "EVALUATION_UPDATE" if before else "EVALUATION_CREATE"
        notify(db, photo.user_id, "PHOTO_REVIEWED", "사진 검수가 완료되었어요", "외적 특징 평가가 프로필에 반영되었습니다.", photo.id)
    else:
        photo.review_status = "REJECTED"
        photo.reject_reason = payload.reject_reason
        after = None
        action = "PHOTO_REJECT"
        notify(db, photo.user_id, "PHOTO_REVIEWED", "사진이 반려되었어요", f"사유: {payload.reject_reason}", photo.id)

    # 평가 수정 시 이전 값을 남긴다 (설계도 §60)
    AuditService.record(
        db,
        admin_id=admin.id,
        action=action,
        target_type="USER_PHOTO",
        target_id=photo.id,
        request=request,
        metadata={"before": before, "after": after, "decision": payload.decision},
    )
    db.commit()
    return {**_photo_summary(photo), "scores": after}


# ---------- 사용자 관리 ----------

def _user_or_404(db: Session, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="사용자를 찾을 수 없습니다.")
    return user


@router.get("/users")
def list_users(
    status_filter: str | None = Query(default=None, alias="status"),
    nickname: str | None = Query(default=None, max_length=20),
    admin: CurrentAdmin = Depends(require_permission("users:read")),
    db: Session = Depends(get_db),
):
    report_counts = (
        db.query(Report.reported_user_id, func.count(Report.id)).group_by(Report.reported_user_id).subquery()
    )
    query = (
        db.query(User, PublicProfile.nickname, report_counts.c[1])
        .outerjoin(PublicProfile, PublicProfile.user_id == User.id)
        .outerjoin(report_counts, report_counts.c.reported_user_id == User.id)
    )
    if status_filter:
        query = query.filter(User.status == status_filter)
    if nickname:
        query = query.filter(PublicProfile.nickname.contains(nickname))
    rows = query.order_by(User.created_at.desc()).limit(100).all()
    return {
        "users": [
            {
                "user_id": str(u.id),
                "subject_code": pseudonymous_code(u.id),
                "nickname": nick,
                "status": u.status,
                "reports_received": reports or 0,
                "created_at": u.created_at.isoformat(),
            }
            for u, nick, reports in rows
        ]
    }


@router.get("/users/{user_id}")
def get_user(
    user_id: uuid.UUID,
    request: Request,
    include_private: bool = False,
    admin: CurrentAdmin = Depends(require_permission("users:read")),
    db: Session = Depends(get_db),
):
    user = _user_or_404(db, user_id)
    profile = db.query(PublicProfile).filter(PublicProfile.user_id == user.id).first()
    result = {
        "user_id": str(user.id),
        "subject_code": pseudonymous_code(user.id),
        "status": user.status,
        "created_at": user.created_at.isoformat(),
        "profile": profile_service.build_card(db, profile) if profile else None,
        "reports_received": profile_service.count(db, db.query(Report.id).filter(Report.reported_user_id == user.id)),
    }
    AuditService.record(db, admin_id=admin.id, action="USER_VIEW", target_type="USER", target_id=user.id, request=request)

    if include_private:
        # 실명·이메일 등은 별도 권한(SUPER_ADMIN)이 있어야 하고, 조회 기록이 남는다
        if "users:private:read" not in admin.permissions:
            db.commit()
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="개인정보 조회 권한이 없습니다.")
        private = db.query(PrivateProfile).filter(PrivateProfile.user_id == user.id).first()
        result["private"] = {
            "email": user.email,
            "real_name": private.real_name if private else None,
            "phone_number": private.phone_number if private else None,
            "student_id": private.student_id if private else None,
            "birth_date": private.birth_date.isoformat() if private else None,
        }
        AuditService.record(db, admin_id=admin.id, action="USER_PRIVATE_VIEW", target_type="USER", target_id=user.id, request=request)
    db.commit()
    return result


@router.patch("/users/{user_id}/status")
def update_user_status(
    user_id: uuid.UUID,
    payload: UserStatusRequest,
    request: Request,
    admin: CurrentAdmin = Depends(require_permission("users:status")),
    db: Session = Depends(get_db),
):
    user = _user_or_404(db, user_id)
    if user.status == "DELETED":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="탈퇴한 계정입니다.")
    before = user.status
    user.status = payload.status
    if payload.status != "ACTIVE":
        revoke_all_user_sessions(db, user.id)  # 즉시 로그아웃
    notify(db, user.id, "ACCOUNT_STATUS", "계정 상태가 변경되었어요", f"현재 상태: {payload.status}")
    AuditService.record(
        db,
        admin_id=admin.id,
        action="USER_STATUS_CHANGE",
        target_type="USER",
        target_id=user.id,
        request=request,
        metadata={"before": before, "after": payload.status, "reason": payload.reason},
    )
    db.commit()
    return {"user_id": str(user.id), "status": user.status}


# ---------- 신고 처리 ----------

@router.get("/reports")
def list_reports(
    status_filter: str | None = Query(default="OPEN", alias="status"),
    admin: CurrentAdmin = Depends(require_permission("reports:read")),
    db: Session = Depends(get_db),
):
    query = db.query(Report)
    if status_filter:
        query = query.filter(Report.status == status_filter)
    rows = query.order_by(Report.created_at.asc()).limit(100).all()
    return {
        "reports": [
            {
                "report_id": str(r.id),
                "reporter_user_id": str(r.reporter_user_id),
                "reported_user_id": str(r.reported_user_id),
                "match_id": str(r.match_id) if r.match_id else None,
                "reason": r.reason,
                "description": r.description,
                "status": r.status,
                "admin_note": r.admin_note,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    }


@router.patch("/reports/{report_id}")
def update_report(
    report_id: uuid.UUID,
    payload: ReportUpdateRequest,
    request: Request,
    admin: CurrentAdmin = Depends(require_permission("reports:update")),
    db: Session = Depends(get_db),
):
    """계정 제재가 필요하면 PATCH /admin/users/{id}/status 를 따로 호출한다."""
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="신고를 찾을 수 없습니다.")
    before = report.status
    report.status = payload.status
    if payload.admin_note is not None:
        report.admin_note = payload.admin_note
    report.reviewed_by_admin_id = admin.id
    if payload.status in ("RESOLVED", "DISMISSED"):
        report.resolved_at = utcnow()
        # 신고자에게는 결과만 알린다 (조치 내용 상세는 알리지 않음)
        notify(db, report.reporter_user_id, "REPORT_RESULT", "신고 처리 결과", "접수하신 신고가 처리되었습니다.", report.id)
    AuditService.record(
        db,
        admin_id=admin.id,
        action="REPORT_UPDATE",
        target_type="REPORT",
        target_id=report.id,
        request=request,
        metadata={"before": before, "after": payload.status},
    )
    db.commit()
    return {"report_id": str(report.id), "status": report.status}


# ---------- 감사 로그 ----------

@router.get("/audit-logs")
def list_audit_logs(
    limit: int = Query(default=100, ge=1, le=500),
    admin: CurrentAdmin = Depends(require_permission("audit:read")),
    db: Session = Depends(get_db),
):
    rows = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
    return {
        "logs": [
            {
                "admin_id": str(r.admin_id) if r.admin_id else None,
                "action": r.action,
                "target_type": r.target_type,
                "target_id": r.target_id,
                "ip": r.ip_address,
                "metadata": r.metadata_json,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    }
