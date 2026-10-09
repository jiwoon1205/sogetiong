"""/api/v1/admin — 관리자 전용. 모든 API는 로그인 + 2단계 인증 + 권한(RBAC)을 확인한다."""

import logging
import uuid
from datetime import timedelta
from io import BytesIO

import pyotp
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response, status
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.rate_limit import client_ip, enforce_rate_limit
from app.core.security import pseudonymous_code, verify_password
from app.core.time import KST, as_utc, kst_today, utcnow
from app.db.session import get_db
from app.deps import CurrentAdmin, get_admin_pending_mfa, get_current_admin, require_permission
from app.models.admin import AdminUser, AuditLog
from app.models.matching import Match, MatchingPreference, Message, Report
from app.models.payment import Payment
from app.models.photo import AppearanceEvaluation, UserPhoto
from app.models.profile import PrivateProfile, PublicProfile
from app.models.university import Department
from app.models.user import User, UserDailyVisit
from app.schemas.admin import (
    GiveLikesRequest,
    AdminLoginRequest,
    AdminTwoFactorRequest,
    EvaluationRequest,
    ReportUpdateRequest,
    AppearanceTierRequest,
    MatchSuspensionRequest,
    MembershipAdjustRequest,
    UserDepartmentRequest,
    UserGenderRequest,
    UserStatusRequest,
)
from app.services import admin_alert_service, audit_service, match_limit_service, membership_service, payment_service, profile_service, vip_service, withdrawal_service
from app.services.email_service import EmailDeliveryError, EmailService
from app.services.notification_service import notify, notify_match_created
from app.services.session_service import (
    clear_admin_cookies,
    create_admin_session,
    revoke_all_user_sessions,
    set_admin_cookies,
)
from app.services.storage_service import get_storage

logger = logging.getLogger(__name__)
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
    audit_service.record(db, admin_id=admin.id, action="ADMIN_LOGIN", target_type="ADMIN", target_id=admin.id, request=request)
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

    today = kst_today()
    active_users = db.query(User.id).filter(User.status == "ACTIVE")

    # 사진 검수까지 끝난 사람 (승인된 사진이 있음)
    approved = db.query(UserPhoto.user_id).filter(UserPhoto.review_status == "APPROVED")

    def visitors_since(day):
        return db.query(UserDailyVisit.user_id).filter(UserDailyVisit.visit_date >= day)

    def visited_since(day, *, photo_approved=False):
        """이 날(한국 시간) 이후로 한 번이라도 접속한 정상 계정 수"""
        q = active_users.filter(User.id.in_(visitors_since(day)))
        if photo_approved:
            q = q.filter(User.id.in_(approved))
        return c(q)

    def gender_count(gender, since=None):
        q = (
            db.query(User.id)
            .join(PublicProfile, PublicProfile.user_id == User.id)
            .filter(User.status == "ACTIVE", PublicProfile.gender == gender)
        )
        if since is not None:  # 활성 사용자만: 이 날 이후 접속 + 사진 검수 완료
            q = q.filter(User.id.in_(visitors_since(since)), User.id.in_(approved))
        return c(q)

    week_start = today - timedelta(days=6)

    return {
        "users_total": c(db.query(User.id)),
        # 활성 = 사진 검수까지 끝났고, 최근 7일(오늘 포함) 안에 접속한 정상 계정 (2026-10-01 변경).
        # 예전에는 "탈퇴·정지 안 한 계정"이라 전체 가입자와 거의 같았다 → 그 숫자는 users_normal로 옮김
        "users_active": visited_since(week_start, photo_approved=True),
        "users_active_today": visited_since(today),
        "users_normal": c(active_users),
        # 성비 (정상 계정 중 프로필을 만든 사람 기준)
        "users_male": gender_count("MALE"),
        "users_female": gender_count("FEMALE"),
        # 활성 사용자(최근 7일 접속)의 남녀 분포 — 대시보드 원그래프용
        "users_active_male": gender_count("MALE", week_start),
        "users_active_female": gender_count("FEMALE", week_start),
        "users_suspended": c(db.query(User.id).filter(User.status.in_(["SUSPENDED", "BANNED"]))),
        # 탈퇴한 사용자 (탈퇴 후 영구 정지한 계정 포함). recent = 최근 7일 안에 탈퇴 → 아직 프로필·사진 열람 가능
        "users_deleted": c(db.query(User.id).filter(User.deleted_at.isnot(None))),
        "users_deleted_recent": c(
            db.query(User.id).filter(
                User.deleted_at.isnot(None),
                User.deleted_at > utcnow() - timedelta(days=get_settings().withdrawn_retention_days),
            )
        ),
        "photos_pending": admin_alert_service.pending_photo_query(db).count(),
        "matches_total": c(db.query(Match.id)),
        "reports_open": c(db.query(Report.id).filter(Report.status.in_(["OPEN", "IN_REVIEW"]))),
        # 가입비 입금 확인 대기 (2026-10-03)
        "payments_pending": c(db.query(Payment.id).filter(Payment.status == "REQUESTED")),
        # 이용권 (2026-10-04 구독제): 지금 이용 중 / VIP / 7일 안에 끝남 (정상 계정, 테스트 계정 제외)
        **_membership_counts(db, c),
    }


def _membership_counts(db: Session, c) -> dict:
    now = utcnow()
    active = db.query(User.id).filter(User.status == "ACTIVE", User.member_until > now)
    return {
        "members_active": c(active),
        "members_vip": c(db.query(User.id).filter(User.status == "ACTIVE", User.vip_until > now)),
        "members_expiring_week": c(active.filter(User.member_until <= now + timedelta(days=7))),
    }


# ---------- 사진 검수 / 외적 평가 ----------
# PHOTO_REVIEWER는 사진과 가명 코드(U1A2B3C)만 본다. 이름·이메일·학번 등은 보이지 않는다 (설계도 §29).

def _photo_or_404(db: Session, photo_id: uuid.UUID) -> UserPhoto:
    photo = db.get(UserPhoto, photo_id)
    if photo is None or photo.upload_status == "DELETED":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="사진을 찾을 수 없습니다.")
    return photo


def _submission_photos(db: Session, photo: UserPhoto) -> list[UserPhoto]:
    """같이 제출한 사진 묶음 전체 (대표 사진 먼저). 예전 사진은 한 장짜리 묶음."""
    if photo.submission_id is None:
        return [photo]
    return (
        db.query(UserPhoto)
        .filter(UserPhoto.submission_id == photo.submission_id, UserPhoto.upload_status != "DELETED")
        .order_by(UserPhoto.position.asc())
        .all()
    )


def _photo_summary(photo: UserPhoto, count: int | None = None) -> dict:
    return {
        "photo_id": str(photo.id),
        "photo_count": count or 1,
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
    """status=PENDING(대기열)에는 "확인 중"도 함께 보여준다.
    상세 화면을 열기만 하고 평가를 끝내지 않은 사진이 대기열에서 사라져 잊히지 않게 하기 위해서다.
    정지·탈퇴한 사용자의 사진은 대기열에 넣지 않는다."""
    if status_filter in ("PENDING", "IN_REVIEW"):
        query = admin_alert_service.pending_photo_query(db)
        if status_filter == "IN_REVIEW":
            query = query.filter(UserPhoto.review_status == "IN_REVIEW")
    else:
        query = db.query(UserPhoto).filter(
            UserPhoto.review_status == status_filter, UserPhoto.upload_status != "DELETED", UserPhoto.position == 0
        )
    if status_filter in ("APPROVED", "REJECTED"):
        # 승인·반려 탭: 최근에 평가한 사진이 맨 위 (내림차순)
        query = query.order_by(UserPhoto.reviewed_at.desc(), UserPhoto.uploaded_at.desc())
    else:
        # 대기 탭: 최근에 올라온 사진이 맨 위 (내림차순)
        query = query.order_by(UserPhoto.uploaded_at.desc())
    photos = query.limit(100).all()
    # 묶음마다 사진이 몇 장인지 (쿼리 1번)
    counts = dict(
        db.query(UserPhoto.submission_id, func.count(UserPhoto.id))
        .filter(UserPhoto.submission_id.in_([p.submission_id for p in photos if p.submission_id]))
        .group_by(UserPhoto.submission_id)
        .all()
    )
    return {"photos": [_photo_summary(p, counts.get(p.submission_id)) for p in photos]}


@router.get("/photo-reviews/{photo_id}")
def get_photo_review(
    photo_id: uuid.UUID,
    admin: CurrentAdmin = Depends(require_permission("photos:read")),
    db: Session = Depends(get_db),
):
    photo = _photo_or_404(db, photo_id)
    group = _submission_photos(db, photo)
    if photo.review_status == "PENDING":
        for p in group:
            if p.review_status == "PENDING":
                p.review_status = "IN_REVIEW"
        db.commit()
    history = (
        db.query(AppearanceEvaluation)
        .filter(AppearanceEvaluation.user_id == photo.user_id)
        .order_by(AppearanceEvaluation.created_at.desc())
        .limit(5)
        .all()
    )
    return {
        **_photo_summary(photo, len(group)),
        "image_url": f"/api/v1/admin/photo-reviews/{photo.id}/image",
        # 함께 제출한 사진 전부 (최대 3장). 묶음 전체를 보고 한 번에 평가한다
        "image_urls": [f"/api/v1/admin/photo-reviews/{p.id}/image" for p in group],
        # 이 사진의 검수 결과 (반려/승인 후 '보기'로 들어왔을 때 보여준다)
        "reject_reason": photo.reject_reason,
        "review_note": photo.review_note,
        "evaluation_history": [
            {**e.scores(), "tier": e.tier, "note": e.evaluation_note, "created_at": e.created_at.isoformat()} for e in history
        ],
    }


def _watermark(data: bytes, text: str) -> bytes:
    """관리자 이메일+시각을 사진에 새겨서, 화면 캡처가 유출되면 누가 봤는지 알 수 있게 한다 (설계도 §39)."""
    # 예전에는 큰 글씨를 6줄이나 찍어서 얼굴이 가려졌다.
    # 이제 작은 글씨를 반투명하게 위·아래 가장자리에만 1줄씩 찍어, 사진 판독을 방해하지 않게 한다.
    with Image.open(BytesIO(data)) as image:
        image = image.convert("RGBA")
        overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        font = ImageFont.load_default(size=max(11, image.width // 70))
        line_h = font.getbbox(text)[3]
        margin = max(6, image.width // 100)
        for y in (margin, image.height - line_h - margin):
            draw.text((margin + 1, y + 1), text, fill=(0, 0, 0, 90), font=font)  # 그림자
            draw.text((margin, y), text, fill=(255, 255, 255, 130), font=font)  # 반투명 흰 글씨
        image = Image.alpha_composite(image, overlay).convert("RGB")
        out = BytesIO()
        image.save(out, format="JPEG", quality=90)
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
    audit_service.record(db, admin_id=admin.id, action="PHOTO_VIEW", target_type="USER_PHOTO", target_id=photo.id, request=request)
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
    background: BackgroundTasks,
    admin: CurrentAdmin = Depends(require_permission("photos:evaluate")),
    db: Session = Depends(get_db),
):
    photo = _photo_or_404(db, photo_id)
    owner = db.get(User, photo.user_id)
    if owner is not None and owner.deleted_at is not None:
        # 탈퇴 후 7일 동안 사진은 열람만 할 수 있다 (평가하면 탈퇴한 사람에게 알림·추천이 생길 수 있음)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="탈퇴한 사용자의 사진은 평가할 수 없습니다.")
    if photo.review_status == "SUPERSEDED":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="새 사진으로 대체된 사진입니다.")
    # 묶음으로 낸 사진은 대표 사진 기준으로 함께 평가한다
    group = _submission_photos(db, photo)
    photo = group[0]
    siblings = group[1:]

    previous = profile_service.latest_evaluations(db, [photo.user_id]).get(photo.user_id)
    before = {**previous.scores(), "tier": previous.tier} if previous else None
    now = utcnow()
    photo.reviewed_at = now
    photo.reviewed_by = admin.id
    # 내부 메모는 승인·반려 상관없이 사진에 저장한다 (예전엔 반려 메모가 어디에도 저장되지 않았다)
    photo.review_note = payload.note.strip() if payload.note and payload.note.strip() else None

    for sibling in siblings:
        sibling.reviewed_at = now
        sibling.reviewed_by = admin.id
        sibling.review_status = "APPROVED" if payload.decision == "APPROVED" else "REJECTED"
        sibling.reject_reason = None if payload.decision == "APPROVED" else payload.reject_reason

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
            tier=payload.tier,
            evaluator_admin_id=admin.id,
            evaluation_note=photo.review_note,
        )
        db.add(evaluation)
        after = {**evaluation.scores(), "tier": evaluation.tier}
        action = "EVALUATION_UPDATE" if before else "EVALUATION_CREATE"
        notify(db, photo.user_id, "PHOTO_REVIEWED", "사진 검수가 완료되었어요", "외적 특징 평가가 프로필에 반영되었습니다.", photo.id)
        _start_membership(db, photo.user_id)
    else:
        photo.review_status = "REJECTED"
        photo.reject_reason = payload.reject_reason
        after = None
        action = "PHOTO_REJECT"
        notify(db, photo.user_id, "PHOTO_REVIEWED", "사진이 반려되었어요", f"사유: {payload.reject_reason}", photo.id)

    # 평가 수정 시 이전 값을 남긴다 (설계도 §60)
    audit_service.record(
        db,
        admin_id=admin.id,
        action=action,
        target_type="USER_PHOTO",
        target_id=photo.id,
        request=request,
        metadata={"before": before, "after": after, "decision": payload.decision},
    )
    db.commit()
    # 대기 사진이 10장 아래로 줄었으면, 다음에 다시 10장이 쌓일 때 알림이 가도록 기록을 지운다
    admin_alert_service.photo_backlog_alert_due(admin_alert_service.pending_photo_query(db).count())

    # 사이트 안 알림만으로는 창을 닫은 사용자가 모른다 → 결과를 메일로도 보낸다 (응답 뒤 발송)
    owner = db.get(User, photo.user_id)
    if owner is not None and owner.status == "ACTIVE":
        if payload.decision == "APPROVED":
            background.add_task(_send_quietly, EmailService.send_photo_approved, owner.email)
        else:
            background.add_task(_send_quietly, EmailService.send_photo_rejected, owner.email, payload.reject_reason)
    # 관리자 응답이라 등급을 보여줘도 된다 (사용자 쪽 API에는 절대 넣지 않음)
    return {
        **_photo_summary(photo, len(group)),
        "scores": {k: v for k, v in after.items() if k != "tier"} if after else None,
        "tier": after["tier"] if after else None,
    }


def _send_quietly(send, *args) -> None:
    """메일 발송이 실패해도 평가 결과는 이미 저장됐고, 사용자는 사이트 안 알림으로도 볼 수 있다."""
    try:
        send(*args)
    except EmailDeliveryError:
        logger.error("photo result email failed")


# ---------- 사용자 관리 ----------

def _user_or_404(db: Session, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="사용자를 찾을 수 없습니다.")
    return user


USER_LIST_LIMIT = 1000


@router.get("/users")
def list_users(
    status_filter: str | None = Query(default=None, alias="status"),
    nickname: str | None = Query(default=None, max_length=20),
    q: str | None = Query(default=None, max_length=20),
    gender: str | None = Query(default=None, pattern="^(MALE|FEMALE)$"),
    membership: str | None = Query(default=None, pattern="^(active|vip|expiring)$"),
    admin: CurrentAdmin = Depends(require_permission("users:read")),
    db: Session = Depends(get_db),
):
    report_counts = (
        db.query(Report.reported_user_id, func.count(Report.id)).group_by(Report.reported_user_id).subquery()
    )
    # 탈퇴하면 공개 프로필이 지워지므로, 탈퇴할 때 남겨 둔 닉네임·성별(users.deleted_*)로 대신한다.
    # 이렇게 해야 닉네임 검색·성별 필터에서도 탈퇴한 사람이 나온다.
    nick_col = func.coalesce(PublicProfile.nickname, User.deleted_nickname)
    gender_col = func.coalesce(PublicProfile.gender, User.deleted_gender)
    query = (
        db.query(User, nick_col, gender_col, report_counts.c[1])
        .outerjoin(PublicProfile, PublicProfile.user_id == User.id)
        .outerjoin(report_counts, report_counts.c.reported_user_id == User.id)
    )
    if status_filter:
        query = query.filter(User.status == status_filter)
    if nickname:
        query = query.filter(nick_col.contains(nickname))
    if q and q.strip():
        # 검색칸 하나로 닉네임 또는 사용자 코드(예: UA38192)를 찾는다 (2026-10-06).
        # 코드는 ID를 비밀 키로 섞어 만든 값이라 DB에 없다 → 사용자마다 계산해서 비교한다 (수백 명이라 금방 끝남).
        term = q.strip()
        code_term = term.upper()
        code_ids = [uid for (uid,) in db.query(User.id) if code_term in pseudonymous_code(uid)]
        query = query.filter(or_(nick_col.contains(term), User.id.in_(code_ids)))
    if gender:
        query = query.filter(gender_col == gender)
    if membership:
        # 현황의 "이용권 이용 중" 칸을 누르면 들어온다 (2026-10-06). 숫자와 똑같은 기준(_membership_counts)으로 거른다.
        now = utcnow()
        query = query.filter(User.status == "ACTIVE")
        if membership == "vip":
            query = query.filter(User.vip_until > now)
        else:
            query = query.filter(User.member_until > now)
            if membership == "expiring":
                query = query.filter(User.member_until <= now + timedelta(days=7))
    # 예전에는 최근 100명만 보여서, 가입자가 100명을 넘으면 오래된 사람(탈퇴자 포함)이 목록에서 사라졌다.
    # 베타 예상 최대 인원(~500명)을 넉넉히 넘게 보여주고, 전체 수(total)를 함께 알려준다.
    total = query.count()
    if membership == "vip":
        query = query.order_by(User.vip_until.asc())  # 곧 끝나는 사람부터
    elif membership:
        query = query.order_by(User.member_until.asc())
    elif status_filter == "DELETED":
        # 탈퇴한 사용자: 마지막 접속이 최근인 사람부터 (접속 기록이 없으면 맨 아래)
        query = query.order_by(User.last_active_at.is_(None), User.last_active_at.desc(), User.created_at.desc())
    else:
        query = query.order_by(User.created_at.desc())
    rows = query.limit(USER_LIST_LIMIT).all()
    stages = _onboarding_stages(db, [u.id for u, _, _, _ in rows])
    return {
        "total": total,
        "users": [
            {
                "user_id": str(u.id),
                "subject_code": pseudonymous_code(u.id),
                "nickname": nick,
                "gender": user_gender,  # MALE / FEMALE / None(프로필 없음)
                "status": u.status,
                "onboarding_stage": stages.get(u.id, "PROFILE"),
                "reports_received": reports or 0,
                "last_active_at": u.last_active_at.isoformat() if u.last_active_at else None,
                "created_at": u.created_at.isoformat(),
                "member_until": u.member_until.isoformat() if u.member_until else None,
                "vip_until": u.vip_until.isoformat() if u.vip_until else None,
            }
            for u, nick, user_gender, reports in rows
        ]
    }


def _onboarding_stages(db: Session, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    """가입 후 어느 단계까지 했는지 (관리자가 "어디서 멈췄는지" 보려고, 2026-10-01 추가).

    PROFILE     : 프로필(학과) 미완료
    PREFERENCES : 매칭 조건 미설정
    PAYMENT     : 첫 이용권 입금 전 (또는 "입금 없음" 처리됨) — 2026-10-03
    PAYMENT_CHECK : "입금했어요"를 누르고 관리자 확인 대기
    PHOTO       : 사진 미제출 (반려 후 다시 안 낸 경우 포함)
    REVIEW      : 사진 검수 대기
    DONE        : 사진 승인됨
    목록에 나온 사람들만 한 번에 조회한다 (사람 수만큼 DB를 부르지 않게).
    """
    if not user_ids:
        return {}
    profile_done = {
        uid
        for (uid,) in db.query(PublicProfile.user_id).filter(
            PublicProfile.user_id.in_(user_ids), PublicProfile.department_id.isnot(None)
        )
    }
    prefs_done = {uid for (uid,) in db.query(MatchingPreference.user_id).filter(MatchingPreference.user_id.in_(user_ids))}
    photo_rows = (
        db.query(UserPhoto.user_id, UserPhoto.review_status)
        .filter(UserPhoto.user_id.in_(user_ids), UserPhoto.upload_status != "DELETED")
        .all()
    )
    approved = {uid for uid, st in photo_rows if st == "APPROVED"}
    unpaid = {
        u.id
        for u in db.query(User).filter(User.id.in_(user_ids)).all()
        if membership_service.needs_first_payment(u, has_approved_photo=u.id in approved)
    }
    payment_status = payment_service.latest_status_by_user(db, list(unpaid))
    pending = {uid for uid, st in photo_rows if st in ("PENDING", "IN_REVIEW")}

    stages = {}
    for uid in user_ids:
        if uid in approved:
            stages[uid] = "DONE"
        elif uid in pending:
            stages[uid] = "REVIEW"
        elif uid not in profile_done:
            stages[uid] = "PROFILE"
        elif uid not in prefs_done:
            stages[uid] = "PREFERENCES"
        elif uid in unpaid:
            stages[uid] = "PAYMENT_CHECK" if payment_status.get(uid) == "REQUESTED" else "PAYMENT"
        else:
            stages[uid] = "PHOTO"
    return stages


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
    private = db.query(PrivateProfile).filter(PrivateProfile.user_id == user.id).first()
    result = {
        "user_id": str(user.id),
        "subject_code": pseudonymous_code(user.id),
        "status": user.status,
        "created_at": user.created_at.isoformat(),
        "last_active_at": user.last_active_at.isoformat() if user.last_active_at else None,
        # 유료 정보 (2026-10-03): 베타 회원 여부, 가입비 확인 시각, VIP 끝나는 시각
        "is_beta_member": user.is_beta_member,
        "signup_paid_at": user.signup_paid_at.isoformat() if user.signup_paid_at else None,
        "vip_until": user.vip_until.isoformat() if user.vip_until else None,
        # 이용권 (2026-10-04 구독제): 끝나는 시각, 아직 시작 안 한 일수(사진 검수 후 시작), 상태
        "member_until": user.member_until.isoformat() if user.member_until else None,
        "member_days_banked": user.member_days_banked or 0,
        "membership_status": membership_service.status(user),
        "membership_free": vip_service.is_vip_tester(user),
        # 무료 체험 좋아요 사용 개수 (2026-10-06)
        "trial_likes_used": max(0, min(user.trial_likes_used or 0, membership_service.trial_limit())),
        "trial_like_limit": membership_service.trial_limit(),
        # 오늘 좋아요 현황 (2026-10-10): 관리자가 "좋아요 더 주기"를 할 때 본다
        "likes_today": _likes_today(db, user),
        # 매칭 정지 (2026-10-05, 관리자만 봄): 켜져 있으면 서로 LIKE해도 매칭이 숨겨진다
        "match_suspended": user.match_suspended,
        "match_suspended_at": user.match_suspended_at.isoformat() if user.match_suspended_at else None,
        "hidden_matches": profile_service.count(
            db,
            db.query(Match.id).filter(
                (Match.user_a_id == user.id) | (Match.user_b_id == user.id), Match.status == "HIDDEN"
            ),
        ),
        "profile": profile_service.build_card(db, profile) if profile else None,
        # 카드는 공개 설정에 따라 캠퍼스·학과가 숨겨질 수 있어서, 관리자에게는 실제 값을 따로 보여준다
        "campus": {"id": str(profile.campus_id), "name": profile.campus.name} if profile else None,
        "department": (
            {"id": str(profile.department_id), "name": profile.department.name} if profile and profile.department else None
        ),
        # 성별·원하는 성별 (사용자는 못 바꾸고, 메일 요청을 받아 관리자가 바꾼다)
        "gender": profile.gender if profile else user.deleted_gender,
        # 탈퇴한 사람의 예전 닉네임 (공개 프로필이 지워져서 따로 남겨 둔 값, 관리자만 봄)
        "deleted_nickname": user.deleted_nickname,
        "preferred_gender": private.preferred_gender if private else None,
        # 외모 등급 (내부 전용). None = 아직 없음 → 추천에 나오지 않는다
        "appearance_tier": profile_service.current_tier(db, user.id),
        "reports_received": profile_service.count(db, db.query(Report.id).filter(Report.reported_user_id == user.id)),
        "deleted_at": user.deleted_at.isoformat() if user.deleted_at else None,
        # 탈퇴자: 프로필·사진이 지워지는(지워진) 시각. 그 전까지는 관리자가 열람할 수 있다 (2026-10-01)
        "data_purge_at": (withdrawal_service.purge_at(user.deleted_at).isoformat() if user.deleted_at else None),
        # 사진 (파일이 남아 있는 것만, 최근 순). 화면에서 '사진 보기'를 눌러야 불러오고, 볼 때마다 감사 로그가 남는다
        "photos": [
            {
                "photo_id": str(p.id),
                "review_status": p.review_status,
                "uploaded_at": p.uploaded_at.isoformat() if p.uploaded_at else None,
                "image_url": f"/api/v1/admin/photo-reviews/{p.id}/image",
            }
            for p in db.query(UserPhoto)
            .filter(UserPhoto.user_id == user.id, UserPhoto.upload_status != "DELETED", UserPhoto.storage_key != "")
            .order_by(UserPhoto.uploaded_at.desc(), UserPhoto.position)
            .limit(12)
        ],
        # 같은 학교 메일로 가입했던 다른 계정 (탈퇴 후 재가입 등). 이메일 자체는 보여주지 않는다.
        "linked_accounts": [
            {
                "user_id": str(u.id),
                "subject_code": pseudonymous_code(u.id),
                "status": u.status,
                "created_at": u.created_at.isoformat(),
                "deleted_at": u.deleted_at.isoformat() if u.deleted_at else None,
            }
            for u in (
                db.query(User)
                .filter(User.email_hash == user.email_hash, User.id != user.id)
                .order_by(User.created_at)
                .all()
                if user.email_hash
                else []
            )
        ],
    }
    audit_service.record(db, admin_id=admin.id, action="USER_VIEW", target_type="USER", target_id=user.id, request=request)

    if include_private:
        # 실명·이메일 등은 별도 권한(SUPER_ADMIN)이 있어야 하고, 조회 기록이 남는다
        if "users:private:read" not in admin.permissions:
            db.commit()
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="개인정보 조회 권한이 없습니다.")
        result["private"] = {
            "email": user.email,
            "real_name": private.real_name if private else None,
            "phone_number": private.phone_number if private else None,
            "student_id": private.student_id if private else None,
            "birth_date": private.birth_date.isoformat() if private else None,
        }
        audit_service.record(db, admin_id=admin.id, action="USER_PRIVATE_VIEW", target_type="USER", target_id=user.id, request=request)
    db.commit()
    return result


@router.post("/users/{user_id}/membership-adjust")
def adjust_user_membership(
    user_id: uuid.UUID,
    payload: MembershipAdjustRequest,
    request: Request,
    admin: CurrentAdmin = Depends(require_permission("payments:confirm")),
    db: Session = Depends(get_db),
):
    """이용권 기간을 며칠 늘리거나 줄인다 (2026-10-04 D8). 최고 관리자만, 사유는 감사 로그에 남는다.

    남아 있으면 끝나는 날에서 더하거나 빼고, 끝났거나 없으면 지금부터 더한다 (빼기는 무시).
    """
    user = _user_or_404(db, user_id)
    if user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="탈퇴한 사용자는 바꿀 수 없습니다.")
    if payload.days == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="0일은 바꿀 게 없습니다.")
    before = user.member_until.isoformat() if user.member_until else None
    membership_service.adjust(user, payload.days)
    after = user.member_until.isoformat() if user.member_until else None
    audit_service.record(
        db,
        admin_id=admin.id,
        action="MEMBERSHIP_ADJUST",
        target_type="USER",
        target_id=user.id,
        request=request,
        metadata={"days": payload.days, "before": before, "after": after, "reason": payload.reason},
    )
    db.commit()
    return {"user_id": str(user.id), "member_until": after, "membership_status": membership_service.status(user)}


@router.post("/users/{user_id}/likes")
def give_user_likes(
    user_id: uuid.UUID,
    payload: GiveLikesRequest,
    request: Request,
    admin: CurrentAdmin = Depends(require_permission("payments:confirm")),
    db: Session = Depends(get_db),
):
    """좋아요를 더 준다 (2026-10-10, 최고 관리자). 이용권·VIP·베타면 "오늘만" 하루 한도에 더하고,
    체험 중이거나 좋아요를 못 하는 사람(체험 다 씀·이용권 끝)은 체험 좋아요를 더 준다. 사용자에게 알림은 없다."""
    user = _user_or_404(db, user_id)
    if user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="탈퇴한 사용자는 바꿀 수 없습니다.")
    before = _likes_today(db, user)
    kind = membership_service.give_likes(user, payload.count)
    db.flush()
    after = _likes_today(db, user)
    audit_service.record(
        db,
        admin_id=admin.id,
        action="LIKES_GIVE",
        target_type="USER",
        target_id=user.id,
        request=request,
        metadata={"count": payload.count, "kind": kind, "before_left": before["left"], "after_left": after["left"], "reason": payload.reason},
    )
    db.commit()
    return {"user_id": str(user.id), "kind": kind, "likes": after}


def _likes_today(db: Session, user: User) -> dict:
    """관리자 화면용 좋아요 현황 (2026-10-10).
    access: paid(하루 한도) / trial(체험 좋아요 남음) / none(좋아요 불가)
    paid면 오늘 보낸 수·오늘 한도·관리자가 준 오늘 추가분, 아니면 남은 체험 좋아요."""
    access = membership_service.like_access(user)
    if access == "paid":
        limit = vip_service.daily_like_limit(user)
        sent = profile_service.likes_sent_today(db, user.id)
        return {"access": access, "sent": sent, "limit": limit, "left": max(0, limit - sent), "bonus_today": vip_service.bonus_likes_today(user)}
    left = membership_service.trial_left(user)
    return {"access": access, "sent": None, "limit": None, "left": left, "bonus_today": 0}


@router.post("/users/{user_id}/vip-adjust")
def adjust_user_vip(
    user_id: uuid.UUID,
    payload: MembershipAdjustRequest,
    request: Request,
    admin: CurrentAdmin = Depends(require_permission("payments:confirm")),
    db: Session = Depends(get_db),
):
    """VIP 기간을 며칠 늘리거나 줄인다 (2026-10-06). 이용권 기간 조정과 같은 규칙, 최고 관리자만.

    남아 있으면 끝나는 날에서 더하거나 빼고, 끝났거나 없으면 지금부터 더한다 (빼기는 무시).
    VIP에는 기본 이용권이 포함되므로(has_membership) 기본 이용권 기간은 따로 건드리지 않는다.
    """
    user = _user_or_404(db, user_id)
    if user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="탈퇴한 사용자는 바꿀 수 없습니다.")
    if payload.days == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="0일은 바꿀 게 없습니다.")
    before = user.vip_until.isoformat() if user.vip_until else None
    membership_service.adjust_vip(user, payload.days)
    after = user.vip_until.isoformat() if user.vip_until else None
    audit_service.record(
        db,
        admin_id=admin.id,
        action="VIP_ADJUST",
        target_type="USER",
        target_id=user.id,
        request=request,
        metadata={"days": payload.days, "before": before, "after": after, "reason": payload.reason},
    )
    db.commit()
    return {"user_id": str(user.id), "vip_until": after, "vip_active": vip_service.has_paid_vip(user)}


@router.patch("/users/{user_id}/status")
def update_user_status(
    user_id: uuid.UUID,
    payload: UserStatusRequest,
    request: Request,
    admin: CurrentAdmin = Depends(require_permission("users:status")),
    db: Session = Depends(get_db),
):
    user = _user_or_404(db, user_id)
    if user.deleted_at is not None:
        # 탈퇴한 계정: 정지(BANNED)로 바꾸면 같은 메일로 재가입할 수 없게 된다. 풀 때는 다시 DELETED로.
        if payload.status not in ("BANNED", "DELETED"):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="탈퇴한 계정은 영구 정지 또는 정지 해제(탈퇴 상태)만 할 수 있습니다.")
    elif payload.status == "DELETED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="탈퇴 처리는 사용자 본인만 할 수 있습니다.")
    before = user.status
    user.status = payload.status
    if payload.status != "ACTIVE":
        revoke_all_user_sessions(db, user.id)  # 즉시 로그아웃
    if user.deleted_at is None:  # 탈퇴한 사람에게는 알림을 보내지 않는다
        notify(db, user.id, "ACCOUNT_STATUS", "계정 상태가 변경되었어요", f"현재 상태: {payload.status}")
    audit_service.record(
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


# ---------- 매칭 정지 (2026-10-05) ----------
# 매칭 정지된 사람은 서로 LIKE해도 매칭이 "숨김(HIDDEN)"으로 생겨서, 두 사람 모두에게 보이지 않는다.
# 본인에게는 절대 알리지 않는다 (알림·화면 문구 없음). 정지를 풀어도 숨겨진 매칭은 그대로 숨김이고,
# 관리자가 "매칭 정지" 화면에서 하나씩 골라 다시 보이게 한다.


@router.patch("/users/{user_id}/match-suspension")
def update_match_suspension(
    user_id: uuid.UUID,
    payload: MatchSuspensionRequest,
    request: Request,
    admin: CurrentAdmin = Depends(require_permission("users:status")),
    db: Session = Depends(get_db),
):
    user = _user_or_404(db, user_id)
    if user.deleted_at is not None and payload.suspended:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="탈퇴한 사용자는 매칭 정지할 수 없습니다.")
    before = user.match_suspended
    if before != payload.suspended:
        user.match_suspended = payload.suspended
        user.match_suspended_at = utcnow() if payload.suspended else None
    # 사용자에게 알림을 보내지 않는다 (notify 없음)
    audit_service.record(
        db,
        admin_id=admin.id,
        action="MATCH_SUSPEND" if payload.suspended else "MATCH_UNSUSPEND",
        target_type="USER",
        target_id=user.id,
        request=request,
        metadata={"before": before, "after": payload.suspended, "reason": payload.reason},
    )
    db.commit()
    return {"user_id": str(user.id), "match_suspended": user.match_suspended}


def _reveal_problem(db: Session, match: Match, users: dict[uuid.UUID, User]) -> str | None:
    """숨김 매칭을 다시 보이게 할 수 없는 이유. 문제가 없으면 None."""
    for uid in (match.user_a_id, match.user_b_id):
        u = users.get(uid)
        if u is None or u.deleted_at is not None or u.status == "DELETED":
            return "탈퇴한 사용자가 있어요"
        if u.status != "ACTIVE":
            return "이용 정지된 사용자가 있어요"
    if profile_service.is_blocked_between(db, match.user_a_id, match.user_b_id):
        return "둘 사이에 차단이 있어요"
    return None


@router.get("/match-suspensions")
def list_match_suspensions(
    admin: CurrentAdmin = Depends(require_permission("users:status")),
    db: Session = Depends(get_db),
):
    """매칭 정지된 사용자 목록 + 숨겨진 매칭 전체 (정지를 이미 푼 사람의 숨김 매칭도 포함)."""
    suspended = (
        db.query(User).filter(User.match_suspended.is_(True)).order_by(User.match_suspended_at.desc()).all()
    )
    hidden = db.query(Match).filter(Match.status == "HIDDEN").order_by(Match.created_at.desc()).all()

    member_ids = {uid for m in hidden for uid in (m.user_a_id, m.user_b_id)} | {u.id for u in suspended}
    users = {u.id: u for u in db.query(User).filter(User.id.in_(member_ids)).all()} if member_ids else {}
    nicknames = _nicknames(db, list(member_ids)) if member_ids else {}
    hidden_counts: dict[uuid.UUID, int] = {}
    for m in hidden:
        for uid in (m.user_a_id, m.user_b_id):
            hidden_counts[uid] = hidden_counts.get(uid, 0) + 1

    def member(uid: uuid.UUID) -> dict:
        u = users.get(uid)
        return {**_person(uid, nicknames), "match_suspended": bool(u and u.match_suspended)}

    # 자동 정지(하루 매칭 3번)인지, 관리자가 직접 건 정지인지: 가장 최근 정지 기록으로 구분한다 (2026-10-06)
    last_suspend: dict[str, AuditLog] = {}
    if suspended:
        rows = (
            db.query(AuditLog)
            .filter(
                AuditLog.action.in_(["MATCH_SUSPEND", match_limit_service.AUTO_ACTION]),
                AuditLog.target_id.in_([str(u.id) for u in suspended]),
            )
            .order_by(AuditLog.created_at.asc())
            .all()
        )
        for row in rows:
            last_suspend[row.target_id] = row

    def suspend_info(u: User) -> dict:
        row = last_suspend.get(str(u.id))
        auto = bool(row and row.action == match_limit_service.AUTO_ACTION)
        reason = (row.metadata_json or {}).get("reason") if row else None
        return {"auto_suspended": auto, "suspend_reason": reason}

    return {
        "users": [
            {
                **_person(u.id, nicknames),
                "status": u.status,
                "match_suspended_at": u.match_suspended_at.isoformat() if u.match_suspended_at else None,
                "hidden_matches": hidden_counts.get(u.id, 0),
                **suspend_info(u),
            }
            for u in suspended
        ],
        "hidden_matches": [
            {
                "match_id": str(m.id),
                "members": [member(m.user_a_id), member(m.user_b_id)],
                "hidden_at": m.created_at.isoformat(),
                "reveal_blocked_reason": _reveal_problem(db, m, users),
            }
            for m in hidden
        ],
    }


@router.post("/matches/{match_id}/reveal")
def reveal_hidden_match(
    match_id: uuid.UUID,
    request: Request,
    admin: CurrentAdmin = Depends(require_permission("users:status")),
    db: Session = Depends(get_db),
):
    """숨겨진 매칭을 두 사람에게 다시 보이게 한다.

    매칭 시각을 지금으로 바꾸고 보통 매칭과 똑같은 알림을 보낸다 → 사용자는 방금 매칭된 것으로 보인다.
    아직 매칭 정지 중인 사람이 있어도 관리자가 골랐으면 보이게 한다.
    """
    match = db.get(Match, match_id)
    if match is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="매칭을 찾을 수 없습니다.")
    if match.status != "HIDDEN":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="숨겨진 매칭이 아닙니다.")
    users = {u.id: u for u in db.query(User).filter(User.id.in_([match.user_a_id, match.user_b_id])).all()}
    problem = _reveal_problem(db, match, users)
    if problem:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"다시 보이게 할 수 없어요: {problem}")
    hidden_at = match.created_at.isoformat()
    match.status = "ACTIVE"
    match.created_at = utcnow()
    for uid in (match.user_a_id, match.user_b_id):
        notify_match_created(db, uid, match.id)
    audit_service.record(
        db,
        admin_id=admin.id,
        action="MATCH_REVEAL",
        target_type="MATCH",
        target_id=match.id,
        request=request,
        metadata={"hidden_at": hidden_at},
    )
    db.commit()
    return {"match_id": str(match.id), "status": match.status}


@router.patch("/users/{user_id}/department")
def update_user_department(
    user_id: uuid.UUID,
    payload: UserDepartmentRequest,
    request: Request,
    admin: CurrentAdmin = Depends(require_permission("users:department")),
    db: Session = Depends(get_db),
):
    """학과 변경 (사용자는 직접 못 바꾼다). 요청 메일이 가입한 학교 메일에서 왔는지 먼저 확인할 것."""
    user = _user_or_404(db, user_id)
    profile = db.query(PublicProfile).filter(PublicProfile.user_id == user.id).first()
    if profile is None or user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="프로필이 없는 계정입니다.")
    dept = db.get(Department, payload.department_id)
    if dept is None or not dept.active or dept.campus_id != profile.campus_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="이 사용자의 캠퍼스에 있는 학과를 골라주세요.")
    before = profile.department_id
    profile.department_id = dept.id
    notify(db, user.id, "PROFILE_UPDATED", "학과가 변경되었어요", f"요청하신 대로 학과를 '{dept.name}'(으)로 바꿨어요.")
    audit_service.record(
        db,
        admin_id=admin.id,
        action="USER_DEPARTMENT_CHANGE",
        target_type="USER",
        target_id=user.id,
        request=request,
        metadata={"before": str(before) if before else None, "after": str(dept.id), "reason": payload.reason},
    )
    db.commit()
    return {"user_id": str(user.id), "department": {"id": str(dept.id), "name": dept.name}}


GENDER_LABEL = {"MALE": "남성", "FEMALE": "여성", "ANY": "상관없음"}


@router.patch("/users/{user_id}/gender")
def update_user_gender(
    user_id: uuid.UUID,
    payload: UserGenderRequest,
    request: Request,
    admin: CurrentAdmin = Depends(require_permission("users:gender")),
    db: Session = Depends(get_db),
):
    """성별·원하는 성별 변경 (사용자는 직접 못 바꾼다). 요청 메일이 가입한 학교 메일에서 왔는지 먼저 확인할 것.

    이미 생긴 LIKE·매칭은 그대로 두고, 이후 추천부터 새 값이 적용된다.
    """
    user = _user_or_404(db, user_id)
    profile = db.query(PublicProfile).filter(PublicProfile.user_id == user.id).first()
    private = db.query(PrivateProfile).filter(PrivateProfile.user_id == user.id).first()
    if profile is None or private is None or user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="프로필이 없는 계정입니다.")

    before = {"gender": profile.gender, "preferred_gender": private.preferred_gender}
    changes = []
    if payload.gender is not None and payload.gender != profile.gender:
        profile.gender = payload.gender
        changes.append(f"성별: {GENDER_LABEL[payload.gender]}")
    if payload.preferred_gender is not None and payload.preferred_gender != private.preferred_gender:
        private.preferred_gender = payload.preferred_gender
        changes.append(f"원하는 성별: {GENDER_LABEL[payload.preferred_gender]}")
    after = {"gender": profile.gender, "preferred_gender": private.preferred_gender}

    if changes:
        notify(db, user.id, "PROFILE_UPDATED", "성별 정보가 변경되었어요", "요청하신 대로 바꿨어요. " + ", ".join(changes))
        audit_service.record(
            db,
            admin_id=admin.id,
            action="USER_GENDER_CHANGE",
            target_type="USER",
            target_id=user.id,
            request=request,
            metadata={"before": before, "after": after, "reason": payload.reason},
        )
    db.commit()
    return {"user_id": str(user.id), **after}


@router.patch("/users/{user_id}/appearance-tier")
def update_user_appearance_tier(
    user_id: uuid.UUID,
    payload: AppearanceTierRequest,
    request: Request,
    admin: CurrentAdmin = Depends(require_permission("photos:evaluate")),
    db: Session = Depends(get_db),
):
    """외모 등급만 다시 정한다 (점수는 그대로). 등급이 없는 예전 평가를 채울 때도 쓴다.

    평가 기록은 지우거나 고치지 않고, 점수를 복사한 새 평가 행을 추가해 이력을 남긴다.
    사용자에게는 알리지 않는다 (등급은 내부 데이터).
    """
    user = _user_or_404(db, user_id)
    if user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="탈퇴한 사용자는 등급을 바꿀 수 없습니다.")
    latest = profile_service.latest_evaluations(db, [user.id]).get(user.id)
    if latest is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="아직 외모 평가를 받지 않은 사용자입니다. 사진 검수에서 먼저 평가해주세요.")
    before = latest.tier
    if before != payload.tier:
        db.add(
            AppearanceEvaluation(
                user_id=user.id,
                photo_id=latest.photo_id,
                overall_impression=latest.overall_impression,
                style=latest.style,
                grooming=latest.grooming,
                photo_vibe=latest.photo_vibe,
                tier=payload.tier,
                evaluator_admin_id=admin.id,
                evaluation_note=latest.evaluation_note,
                # 같은 시각이면 "최신" 판단이 흔들리므로 이전 평가보다 확실히 뒤로
                created_at=max(utcnow(), as_utc(latest.created_at) + timedelta(microseconds=1)),
            )
        )
        audit_service.record(
            db,
            admin_id=admin.id,
            action="EVALUATION_TIER_CHANGE",
            target_type="USER",
            target_id=user.id,
            request=request,
            metadata={"before": before, "after": payload.tier, "reason": payload.reason},
        )
        _start_membership(db, user.id)
    db.commit()
    return {"user_id": str(user.id), "appearance_tier": payload.tier}


def _start_membership(db: Session, user_id: uuid.UUID) -> None:
    """등급이 정해져 추천이 열리면, 사진 검수 전에 낸 이용권(쌓아 둔 일수)을 지금부터 센다 (2026-10-04 D1)."""
    owner = db.get(User, user_id)
    if owner is None or not (owner.member_days_banked or 0):
        return
    db.flush()  # 방금 추가한 평가·사진 상태가 can_start에 보이게
    if membership_service.start_banked(db, owner):
        days = (owner.member_until and membership_service.days_left(owner)) or get_settings().membership_days
        notify(db, owner.id, "MEMBERSHIP_STARTED", "이용권이 시작되었어요", f"오늘부터 {days}일 동안 추천을 볼 수 있어요.", None)


# ---------- 대화 열람 ----------
# 운영 정책: 권한(chats:read)이 있는 관리자는 모든 대화를 볼 수 있다.
# 대신 대화를 열 때마다 감사 로그(CHAT_VIEW)에 누가·언제·어느 대화를 봤는지 남긴다.


def _nicknames(db: Session, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    rows = db.query(PublicProfile.user_id, PublicProfile.nickname).filter(PublicProfile.user_id.in_(user_ids)).all()
    result = dict(rows)
    # 탈퇴한 사람은 공개 프로필이 없으니, 탈퇴할 때 남겨 둔 닉네임으로 채운다 (관리자 화면 전용)
    missing = [uid for uid in user_ids if uid not in result]
    if missing:
        result.update(
            db.query(User.id, User.deleted_nickname).filter(User.id.in_(missing), User.deleted_nickname.isnot(None)).all()
        )
    return result


def _person(user_id: uuid.UUID, nicknames: dict[uuid.UUID, str]) -> dict:
    return {
        "user_id": str(user_id),
        "subject_code": pseudonymous_code(user_id),
        "nickname": nicknames.get(user_id),  # 탈퇴하면 None
    }


@router.get("/matches")
def list_all_matches(
    status_filter: str | None = Query(default=None, alias="status", pattern="^(ACTIVE|UNMATCHED|BLOCKED|HIDDEN)$"),
    nickname: str | None = Query(default=None, max_length=20),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    admin: CurrentAdmin = Depends(require_permission("chats:read")),
    db: Session = Depends(get_db),
):
    """매칭으로 생긴 모든 대화방 목록 (신고 여부와 상관없음, 끝난 대화 포함).

    최근에 메시지가 오간 대화방이 위에 온다 (메시지가 없으면 매칭 시각 기준).
    목록에는 메시지 내용이 없으므로 감사 로그를 남기지 않는다. 내용을 열 때 CHAT_VIEW가 남는다.
    """
    stats = (
        db.query(
            Message.match_id.label("match_id"),
            func.count(Message.id).label("message_count"),
            func.max(Message.created_at).label("last_message_at"),
        )
        .group_by(Message.match_id)
        .subquery()
    )
    activity = func.coalesce(stats.c.last_message_at, Match.created_at)
    query = db.query(Match, stats.c.message_count, stats.c.last_message_at).outerjoin(stats, stats.c.match_id == Match.id)
    if status_filter:
        query = query.filter(Match.status == status_filter)
    if nickname:
        members = db.query(PublicProfile.user_id).filter(PublicProfile.nickname.contains(nickname))
        # 탈퇴한 사람은 탈퇴할 때 남겨 둔 닉네임으로 찾는다
        left = db.query(User.id).filter(User.deleted_nickname.contains(nickname))
        query = query.filter(
            Match.user_a_id.in_(members) | Match.user_b_id.in_(members) | Match.user_a_id.in_(left) | Match.user_b_id.in_(left)
        )
    rows = query.order_by(activity.desc(), Match.id).offset(offset).limit(limit + 1).all()
    has_more = len(rows) > limit
    rows = rows[:limit]

    nicknames = _nicknames(db, [uid for m, _, _ in rows for uid in (m.user_a_id, m.user_b_id)])
    return {
        "matches": [
            {
                "match_id": str(m.id),
                "members": [_person(m.user_a_id, nicknames), _person(m.user_b_id, nicknames)],
                "status": m.status,
                "matched_at": m.created_at.isoformat(),
                "ended_at": m.ended_at.isoformat() if m.ended_at else None,
                "message_count": count or 0,
                "last_message_at": last.isoformat() if last else None,
            }
            for m, count, last in rows
        ],
        "has_more": has_more,
    }


@router.get("/users/{user_id}/matches")
def list_user_matches(
    user_id: uuid.UUID,
    admin: CurrentAdmin = Depends(require_permission("chats:read")),
    db: Session = Depends(get_db),
):
    """이 사용자의 모든 대화방 목록 (끝난 대화 포함). 메시지 내용은 없다."""
    user = _user_or_404(db, user_id)
    matches = (
        db.query(Match)
        .filter((Match.user_a_id == user.id) | (Match.user_b_id == user.id))
        .order_by(Match.created_at.desc())
        .all()
    )
    match_ids = [m.id for m in matches]
    stats = {}
    if match_ids:
        stats = {
            mid: (count, last)
            for mid, count, last in db.query(Message.match_id, func.count(Message.id), func.max(Message.created_at))
            .filter(Message.match_id.in_(match_ids))
            .group_by(Message.match_id)
        }
    nicknames = _nicknames(db, [m.partner_of(user.id) for m in matches])
    result = []
    for m in matches:
        count, last = stats.get(m.id, (0, None))
        result.append(
            {
                "match_id": str(m.id),
                "partner": _person(m.partner_of(user.id), nicknames),
                "status": m.status,
                "matched_at": m.created_at.isoformat(),
                "ended_at": m.ended_at.isoformat() if m.ended_at else None,
                "message_count": count,
                "last_message_at": last.isoformat() if last else None,
            }
        )
    return {"matches": result}


@router.get("/matches/{match_id}/messages")
def read_match_messages(
    match_id: uuid.UUID,
    request: Request,
    before: uuid.UUID | None = None,
    limit: int = Query(default=200, ge=1, le=500),
    admin: CurrentAdmin = Depends(require_permission("chats:read")),
    db: Session = Depends(get_db),
):
    """대화 내용 열람. 최신 limit개, 더 이전 것은 before=<가장 오래된 message_id>."""
    match = db.get(Match, match_id)
    if match is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="대화방을 찾을 수 없습니다.")

    query = db.query(Message).filter(Message.match_id == match.id)
    if before:
        anchor = db.get(Message, before)
        if anchor and anchor.match_id == match.id:
            query = query.filter(Message.created_at < anchor.created_at)
    rows = query.order_by(Message.created_at.desc()).limit(limit + 1).all()
    has_more = len(rows) > limit
    rows = list(reversed(rows[:limit]))

    nicknames = _nicknames(db, [match.user_a_id, match.user_b_id])
    audit_service.record(
        db,
        admin_id=admin.id,
        action="CHAT_VIEW",
        target_type="MATCH",
        target_id=match.id,
        request=request,
        metadata={"messages_shown": len(rows), "before": str(before) if before else None},
    )
    db.commit()
    return {
        "match_id": str(match.id),
        "status": match.status,
        "matched_at": match.created_at.isoformat(),
        "ended_at": match.ended_at.isoformat() if match.ended_at else None,
        "members": [_person(match.user_a_id, nicknames), _person(match.user_b_id, nicknames)],
        "messages": [
            {
                "message_id": str(m.id),
                "sender_subject_code": pseudonymous_code(m.sender_user_id),
                "body": m.body,
                "sent_at": m.created_at.isoformat(),
            }
            for m in rows
        ],
        "has_more": has_more,
    }


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
    audit_service.record(
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


# ---------- 가입비 입금 확인 (2026-10-03) ----------
# 최고 관리자(payments:confirm)만. 결제 코드·금액만 보여주고 닉네임·이메일은 보여주지 않는다 (익명성).
# 운영자는 은행 앱의 입금자명(결제 코드)·금액과 이 목록을 맞춰 본다.

PAYMENT_HISTORY_LIMIT = 300


def _payment_row(
    p: Payment, user_status: str | None, match_suspended: bool, admin_emails: dict, reviewed: set, started: set
) -> dict:
    return {
        "payment_id": str(p.id),
        "kind": p.kind,  # SIGNUP(기본 이용권, 예전 이름 가입비) / VIP
        "code": p.code,
        "amount": p.amount,
        "status": p.status,
        "user_status": user_status,  # ACTIVE / SUSPENDED / BANNED / DELETED
        # 매칭 정지 중인 사람의 결제 (2026-10-05): 관리자 화면에만 경고를 띄운다. 사용자 화면은 그대로.
        # 돈을 받기 전에 정지를 풀지, "입금 없음"으로 돌려보낼지 관리자가 정한다. 정지된 사람만 상세 화면 링크용 ID를 준다.
        "match_suspended": match_suspended,
        "user_id": str(p.user_id) if match_suspended else None,
        "requested_at": p.requested_at.isoformat() if p.requested_at else None,
        "processed_at": p.processed_at.isoformat() if p.processed_at else None,
        "processed_by": admin_emails.get(p.processed_by_admin_id),
        # 환불은 기본 이용권만: 입금 확인 + 사진 검수를 한 번도 안 받음 + 이용권이 아직 시작 전 (2026-10-04 D6).
        # 연장 결제(이미 이용권을 쓰기 시작한 사람)와 VIP는 확인 후 환불 없음.
        "refundable": p.kind == "SIGNUP" and p.status == "CONFIRMED" and p.user_id not in reviewed and p.user_id not in started,
    }


@router.get("/payments")
def list_payments(
    view: str = Query(default="pending", pattern="^(pending|history)$"),
    admin: CurrentAdmin = Depends(require_permission("payments:confirm")),
    db: Session = Depends(get_db),
):
    """pending = 확인 대기 (오래된 순), history = 처리한 내역 (최근 순)."""
    query = db.query(Payment, User.status, User.match_suspended).join(User, User.id == Payment.user_id)
    if view == "pending":
        rows = query.filter(Payment.status == "REQUESTED").order_by(Payment.requested_at.asc()).all()
    else:
        rows = (
            query.filter(Payment.status.in_(["CONFIRMED", "REJECTED", "REFUNDED"]))
            .order_by(Payment.processed_at.desc())
            .limit(PAYMENT_HISTORY_LIMIT)
            .all()
        )
    admin_ids = {p.processed_by_admin_id for p, _, _ in rows if p.processed_by_admin_id}
    admin_emails = dict(db.query(AdminUser.id, AdminUser.email).filter(AdminUser.id.in_(admin_ids)).all()) if admin_ids else {}
    confirmed_users = [p.user_id for p, _, _ in rows if p.status == "CONFIRMED"]
    reviewed = (
        {
            uid
            for (uid,) in db.query(UserPhoto.user_id)
            .filter(UserPhoto.user_id.in_(confirmed_users), UserPhoto.reviewed_at.isnot(None))
            .distinct()
        }
        if confirmed_users
        else set()
    )
    started = (
        {uid for (uid,) in db.query(User.id).filter(User.id.in_(confirmed_users), User.member_until.isnot(None))}
        if confirmed_users
        else set()
    )
    return {"payments": [_payment_row(p, st, bool(ms), admin_emails, reviewed, started) for p, st, ms in rows]}


def _payment_or_404(db: Session, payment_id: uuid.UUID) -> Payment:
    payment = db.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="결제를 찾을 수 없습니다.")
    return payment


def _record_payment(db: Session, admin: CurrentAdmin, request: Request, payment: Payment, action: str, before: str):
    audit_service.record(
        db,
        admin_id=admin.id,
        action=action,
        target_type="PAYMENT",
        target_id=payment.id,
        request=request,
        metadata={"code": payment.code, "amount": payment.amount, "before": before, "after": payment.status},
    )


@router.post("/payments/{payment_id}/confirm")
def confirm_payment(
    payment_id: uuid.UUID,
    request: Request,
    admin: CurrentAdmin = Depends(require_permission("payments:confirm")),
    db: Session = Depends(get_db),
):
    """입금 확인 → 사용자는 사진을 낼 수 있다. "입금 없음"으로 잘못 처리한 건도 다시 확인할 수 있다."""
    payment = _payment_or_404(db, payment_id)
    if payment.status not in ("REQUESTED", "REJECTED"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="확인 대기 중인 결제가 아닙니다.")
    before = payment.status
    now = utcnow()
    payment.status = "CONFIRMED"
    payment.processed_at = now
    payment.processed_by_admin_id = admin.id
    user = db.get(User, payment.user_id)
    if user is not None:
        # 이용권·VIP를 살 때마다 "사진 바로 재검토 1회" (2026-10-06). 체험 종료는 add_membership/add_vip가 한다
        membership_service.grant_rereview(user, now)
    # 받는 일수: "입금했어요"를 누른 시각 기준. 베타 기간(OPEN_AT 전)이면 4주, 정식 배포 뒤면 2주 (2026-10-06)
    days = membership_service.period_days(payment.kind, payment.requested_at or now)
    if user is not None and payment.kind == "VIP":
        # 확인한 순간부터 VIP 기간. 남아 있던 기본 이용권은 VIP 뒤로 밀린다 (2026-10-04 구독제)
        membership_service.add_vip(db, user, now, days)
        notify(
            db,
            user.id,
            "VIP_STARTED",
            "VIP가 시작되었어요",
            f"{days}일 동안 VIP 혜택을 받을 수 있어요. '받은 LIKE'에서 나를 LIKE한 사람을 확인해 보세요.",
            payment.id,
        )
    elif user is not None:
        if user.signup_paid_at is None:
            user.signup_paid_at = now  # 첫 결제 시각 (기록용)
        membership_service.add_membership(db, user, now, days)
        if user.member_until is None:
            body = "사진을 제출해 주세요. 사진 검수가 끝나 추천이 열리는 날부터 이용권 기간이 시작돼요."
        else:
            until = as_utc(user.member_until).astimezone(KST) - timedelta(seconds=1)
            body = f"이용권이 {until.month}월 {until.day}일 밤 12시까지예요."
        notify(db, user.id, "PAYMENT_CONFIRMED", "입금이 확인되었어요", body, payment.id)
    _record_payment(db, admin, request, payment, "PAYMENT_CONFIRM", before)
    db.commit()
    return {"payment_id": str(payment.id), "status": payment.status}


@router.post("/payments/{payment_id}/reject")
def reject_payment(
    payment_id: uuid.UUID,
    request: Request,
    admin: CurrentAdmin = Depends(require_permission("payments:confirm")),
    db: Session = Depends(get_db),
):
    """입금 없음 (금액·입금자명이 맞는 입금을 못 찾음). 사용자는 확인 후 다시 "입금했어요"를 누를 수 있다."""
    payment = _payment_or_404(db, payment_id)
    if payment.status != "REQUESTED":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="확인 대기 중인 결제가 아닙니다.")
    payment.status = "REJECTED"
    payment.processed_at = utcnow()
    payment.processed_by_admin_id = admin.id
    notify(
        db,
        payment.user_id,
        "PAYMENT_REJECTED",
        "입금이 확인되지 않았어요",
        f"금액({payment.amount:,}원)과 입금자명(결제 코드 {payment.code})을 확인한 뒤 다시 알려 주세요.",
        payment.id,
    )
    _record_payment(db, admin, request, payment, "PAYMENT_REJECT", "REQUESTED")
    db.commit()
    return {"payment_id": str(payment.id), "status": payment.status}


@router.post("/payments/{payment_id}/refund")
def refund_payment(
    payment_id: uuid.UUID,
    request: Request,
    admin: CurrentAdmin = Depends(require_permission("payments:confirm")),
    db: Session = Depends(get_db),
):
    """환불 처리 (운영자가 사용자 계좌로 직접 송금한 뒤 누른다).

    사진 검수를 한 번이라도 받았으면 (반려 포함) 환불하지 않는다. 환불하면 다시 입금 전 상태가 되고,
    아직 검수 전인 사진은 대기열에서 뺀다.
    """
    payment = _payment_or_404(db, payment_id)
    if payment.kind != "SIGNUP":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="VIP는 입금 확인 후 환불하지 않습니다.")
    if payment.status != "CONFIRMED":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="입금 확인된 결제만 환불할 수 있습니다.")
    if payment_service.has_been_reviewed(db, payment.user_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="사진 검수를 받은 사용자는 환불할 수 없습니다.")
    owner = db.get(User, payment.user_id)
    if owner is not None and owner.member_until is not None:
        # 이미 이용권을 쓰기 시작한 사람의 결제(연장 등)는 환불하지 않는다 (2026-10-04 D6)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이용권이 시작된 뒤에는 환불하지 않습니다.")
    payment.status = "REFUNDED"
    payment.processed_at = utcnow()
    payment.processed_by_admin_id = admin.id
    user = owner
    if user is not None:
        # 쌓아 둔 일수에서 이 결제만큼 뺀다. 남은 게 없으면 다시 "첫 입금 전" 상태 → 사진을 낼 수 없다.
        days = membership_service.period_days("SIGNUP", payment.requested_at or payment.processed_at)
        user.member_days_banked = max(0, (user.member_days_banked or 0) - days)
        if user.member_days_banked == 0:
            user.signup_paid_at = None
    db.query(UserPhoto).filter(
        UserPhoto.user_id == payment.user_id, UserPhoto.review_status.in_(["PENDING", "IN_REVIEW"])
    ).update({"review_status": "SUPERSEDED"}, synchronize_session=False)
    _record_payment(db, admin, request, payment, "PAYMENT_REFUND", "CONFIRMED")
    db.commit()
    return {"payment_id": str(payment.id), "status": payment.status}


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
