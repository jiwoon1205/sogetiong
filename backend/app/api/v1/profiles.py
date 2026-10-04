"""/api/v1/me — 내 계정, 내 공개 프로필, 매칭 조건, 사진, 외적 평가."""

import uuid
from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.rate_limit import enforce_rate_limit
from app.core.security import verify_password
from app.core.time import as_utc, kst_day_start, utcnow
from app.db.session import get_db
from app.deps import CurrentUser, get_current_user
from app.models.matching import Match, MatchingPreference, PreferredCampus
from app.models.photo import AppearanceEvaluation, UserPhoto
from app.models.profile import Interest, PublicProfile, UserInterest
from app.models.university import Campus, Department
from app.schemas.auth import DeleteAccountRequest
from app.schemas.profile import PreferencesRequest, ProfileUpdateRequest
from app.services import admin_alert_service, auth_service, membership_service, payment_service, profile_service, vip_service
from app.services.email_service import EmailService
from app.services.session_service import clear_user_cookies, revoke_all_user_sessions
from app.services.storage_service import PhotoValidationError, get_storage, new_storage_key, process_upload

router = APIRouter()


def _my_profile(db: Session, current: CurrentUser) -> PublicProfile:
    profile = db.query(PublicProfile).filter(PublicProfile.user_id == current.id).first()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="프로필이 없습니다.")
    return profile


def _latest_photo(db: Session, current: CurrentUser) -> UserPhoto | None:
    return db.query(UserPhoto).filter(UserPhoto.user_id == current.id).order_by(UserPhoto.uploaded_at.desc()).first()


def _profile_done(db: Session, current: CurrentUser) -> bool:
    profile = db.query(PublicProfile).filter(PublicProfile.user_id == current.id).first()
    return profile is not None and profile.department_id is not None and profile.show_campus is not None


def department_locked_message() -> str:
    return (
        "학과는 한 번 정하면 바꿀 수 없어요. 잘못 선택했다면 가입한 학교 메일로 "
        f"{get_settings().support_email} 에 바꿀 학과를 알려주세요. 운영진이 확인 후 바꿔드려요."
    )


def gender_locked_message() -> str:
    return (
        "성별과 원하는 성별은 가입할 때 정하면 바꿀 수 없어요. 잘못 선택했다면 가입한 학교 메일로 "
        f"{get_settings().support_email} 에 바꿀 내용을 알려주세요. 운영진이 확인 후 바꿔드려요."
    )


# ---------- 계정 ----------

@router.get("/me")
def get_me(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """본인에게는 본인 이메일을 보여줘도 된다. 다른 사람의 정보는 없다."""
    latest_photo = _latest_photo(db, current)
    has_prefs = db.query(MatchingPreference.id).filter(MatchingPreference.user_id == current.id).first() is not None
    return {
        "email": current.user.email,
        "status": current.user.status,
        "university_id": str(current.user.university_id),
        "onboarding": {
            # 프로필 작성 완료 = 학과와 공개 여부까지 고름
            "profile_done": _profile_done(db, current),
            "photo_status": latest_photo.review_status if latest_photo else "NOT_SUBMITTED",
            "preferences_done": has_prefs,
            # 예전에 승인된 사진이 있으면 (재검토가 반려돼도) 가입 과정은 끝난 것
            "photo_approved": profile_service.has_approved_photo(db, current.id),
            # 첫 이용권 (2026-10-03, 2026-10-04 구독제): 매칭 조건 다음, 사진 전에 입금이 확인돼야 한다
            "payment_required": membership_service.needs_first_payment(
                current.user, has_approved_photo=profile_service.has_approved_photo(db, current.id)
            ),
            # 가입 단계 표시에 "이용권" 단계를 넣을지 (유료화를 켰고, 테스트 계정이 아님)
            "pays_signup_fee": membership_service.enabled() and not vip_service.is_vip_tester(current.user),
        },
        # 이용권 (2026-10-04 구독제): 남은 기간 표시·만료 화면용
        "membership": membership_service.view(current.user),
        # VIP (2026-10-03). visible = "받은 LIKE" 탭을 보여줄지 (정식 오픈 전에는 테스트 계정만)
        "vip": {
            "visible": vip_service.feature_visible(current.user),
            "active": vip_service.is_vip(current.user),
            "until": current.user.vip_until.isoformat() if vip_service.has_paid_vip(current.user) else None,
        },
    }


@router.delete("/me")
def delete_me(
    payload: DeleteAccountRequest,
    response: Response,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """회원 탈퇴 (설계도 §45, 2026-10-01 변경).

    바로: 로그인 세션 삭제, 진행 중인 대화 종료, 이메일 익명화(지문만 보관), 상태 DELETED
          → 다른 사용자에게는 바로 보이지 않는다 (추천·프로필은 정상 계정만 보여줌)
    7일 보관 후 자동 삭제: 공개 프로필, 관심사, 매칭 조건, 사진 파일 (withdrawal_service.purge_expired)
          → 그동안 관리자가 신고·분쟁 확인용으로 열람할 수 있다
    계속 보관: 계정 기본정보, private profile, 신고·채팅 기록, 탈퇴 전 닉네임·성별(관리자 검색용)
    TODO(정식 배포 전): 계속 보관하는 정보의 보관 기간을 정하고 자동 파기 추가
    """
    if not verify_password(payload.password, current.user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="비밀번호가 올바르지 않습니다.")

    uid = current.id
    # 7일 뒤 공개 프로필이 지워져도 관리자가 찾을 수 있게 닉네임·성별을 따로 남겨 둔다
    profile = db.query(PublicProfile).filter(PublicProfile.user_id == uid).first()
    if profile is not None:
        current.user.deleted_nickname = profile.nickname
        current.user.deleted_gender = profile.gender
    now = utcnow()
    db.query(Match).filter(((Match.user_a_id == uid) | (Match.user_b_id == uid)) & (Match.status == "ACTIVE")).update(
        {"status": "UNMATCHED", "ended_at": now}, synchronize_session=False
    )
    # 이메일은 지문만 남기고 가짜 주소로 바꾼다 → 같은 학교 메일로 다시 가입할 수 있다
    current.user.email_hash = auth_service.email_fingerprint(current.user.email)
    current.user.email = auth_service.anonymized_email(uid)
    current.user.status = "DELETED"
    current.user.deleted_at = now
    revoke_all_user_sessions(db, uid)
    db.commit()
    clear_user_cookies(response)
    return {"message": "탈퇴가 완료되었습니다."}


# ---------- 공개 프로필 ----------

@router.get("/me/profile")
def get_my_profile(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """다른 사람에게 보이는 내 카드 + 편집에 필요한 값."""
    profile = _my_profile(db, current)
    card = profile_service.build_card(db, profile)
    card["campus_id"] = str(profile.campus_id)
    card["department_id"] = str(profile.department_id) if profile.department_id else None
    card["department_name"] = profile.department.name if profile.department else None
    card["campus_name"] = profile.campus.name if profile.campus else None
    card["show_department"] = profile.show_department
    card["show_campus"] = profile.show_campus
    card["department_locked"] = profile.department_id is not None
    return card


@router.patch("/me/profile")
def update_my_profile(
    payload: ProfileUpdateRequest,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _my_profile(db, current)
    data = payload.model_dump(exclude_unset=True)

    if "nickname" in data and payload.nickname:
        profile.nickname = payload.nickname.strip()
    if payload.department_id is not None and payload.department_id != profile.department_id:
        # 학과는 처음 한 번만 고를 수 있다 ("같은 과 제외"를 피하려고 학과를 바꾸는 꼼수 방지)
        if profile.department_id is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=department_locked_message())
        dept = db.get(Department, payload.department_id)
        # 학과는 내 캠퍼스 소속이어야 한다
        if dept is None or dept.campus_id != profile.campus_id or not dept.active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="학과를 다시 선택해주세요.")
        # 학과를 처음 고를 때 캠퍼스·학과 공개 여부도 직접 골라야 한다 (정해진 기본값 없음)
        if payload.show_department is None or (payload.show_campus is None and profile.show_campus is None):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="캠퍼스와 학과를 다른 학생에게 보여줄지 골라주세요.")
        profile.department_id = dept.id
    if payload.show_department is not None:
        profile.show_department = payload.show_department
    if payload.show_campus is not None:
        profile.show_campus = payload.show_campus
    # 얼굴상·키: 목록 밖 값이나 범위 밖 키는 위 ProfileUpdateRequest가 422로 막는다
    for field in ("face_type", "height_cm"):
        if field in data:
            setattr(profile, field, data[field])
    for field in ("mbti", "bio", "ideal_type"):
        if field in data:
            value = data[field]
            setattr(profile, field, value.strip() if isinstance(value, str) and value.strip() else None)

    if payload.interests is not None:
        names = {n.strip() for n in payload.interests if n.strip()}
        interests = db.query(Interest).filter(Interest.name.in_(names)).all() if names else []
        if len(interests) != len(names):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="목록에 있는 관심사만 선택할 수 있습니다.")
        db.query(UserInterest).filter(UserInterest.user_id == current.id).delete(synchronize_session=False)
        db.add_all([UserInterest(user_id=current.id, interest_id=i.id) for i in interests])

    db.commit()
    db.refresh(profile)
    return get_my_profile(current, db)


# ---------- 매칭 조건 (Layer 2: 본인만 볼 수 있음) ----------

@router.get("/me/preferences")
def get_my_preferences(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    prefs = profile_service.preferences_of(db, [current.id]).get(current.id)
    # 원하는 성별은 가입할 때 정해서 바꿀 수 없다 → 보여주기만 한다
    preferred_gender = profile_service.preferred_genders_of(db, [current.id]).get(current.id, "ANY")
    if prefs is None:
        return {"configured": False, "preferred_gender": preferred_gender, "gender_locked_message": gender_locked_message(), **_age_bounds()}
    return {
        **_age_bounds(),
        "configured": True,
        "preferred_gender": preferred_gender,
        "gender_locked_message": gender_locked_message(),
        "min_age": prefs.min_age,
        "max_age": prefs.max_age,
        # 둘 다 비어 있으면 "나이 상관없음"
        "age_any": prefs.min_age is None and prefs.max_age is None,
        "campus_mode": prefs.campus_mode,
        "campus_ids": sorted(str(i) for i in prefs.campus_ids),
        "exclude_same_department": prefs.exclude_same_department,
        "changes_left_today": _changes_left(db, current),
        "changes_per_day": get_settings().preferences_changes_per_day,
    }


def _age_bounds() -> dict:
    """나이 가로 바의 양 끝 (화면이 이 값으로 바를 그린다). 왼쪽 = 가입 가능한 최소 나이, 오른쪽 = "N세 이상"."""
    settings = get_settings()
    return {"age_floor": settings.min_age, "age_cap": settings.preference_age_cap}


def _normalize_age_range(min_age: int | None, max_age: int | None) -> tuple[int | None, int | None]:
    """가로 바 기준으로 나이 범위를 정리한다.

    - 최소 나이가 가입 가능한 나이보다 작으면 400 (아래 put에서 처리)
    - 최소 나이가 오른쪽 끝(35)보다 크면 오른쪽 끝으로 맞춘다 ("35세 이상")
    - 최대 나이가 오른쪽 끝(35) 이상이면 비운다 = 위쪽 제한 없음 ("35세 이상")
    """
    cap = get_settings().preference_age_cap
    if min_age is not None and min_age > cap:
        min_age = cap
    if max_age is not None and max_age >= cap:
        max_age = None
    return min_age, max_age


def _window_expired(pref: MatchingPreference, now) -> bool:
    """오늘(한국 시간) 처음 바꾸는 것인지.

    하루 3번은 한국 시간 자정에 다시 채워진다 (하루 LIKE 5개와 같은 기준).
    예전에는 "처음 바꾼 때부터 24시간"이라, 밤 11시에 바꾸면 다음 날 밤 11시까지 안 풀렸다 (2026-10-02 민원).
    """
    started = pref.change_window_started_at
    return started is None or as_utc(started) < kst_day_start(now)


def _changes_left(db: Session, current: CurrentUser) -> int:
    limit = get_settings().preferences_changes_per_day
    pref = db.query(MatchingPreference).filter(MatchingPreference.user_id == current.id).first()
    if pref is None or _window_expired(pref, utcnow()):
        return limit
    return max(0, limit - pref.changes_in_window)


@router.put("/me/preferences")
def put_my_preferences(
    payload: PreferencesRequest,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    if payload.min_age is not None and payload.min_age < settings.min_age:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"최소 나이는 {settings.min_age}세 이상이어야 합니다.")
    min_age, max_age = _normalize_age_range(payload.min_age, payload.max_age)

    uni = current.user.university_id
    campus_ids = set(payload.campus_ids) if payload.campus_mode == "SELECTED" else set()
    if campus_ids:
        valid = {c for (c,) in db.query(Campus.id).filter(Campus.id.in_(campus_ids), Campus.university_id == uni)}
        if valid != campus_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="캠퍼스를 다시 선택해주세요.")

    pref = db.query(MatchingPreference).filter(MatchingPreference.user_id == current.id).first()
    if pref is None:
        # 처음 저장(온보딩)은 변경 횟수에 세지 않는다
        pref = MatchingPreference(user_id=current.id)
        db.add(pref)
    else:
        before = profile_service.preferences_of(db, [current.id]).get(current.id)
        changed = before is None or (
            before.min_age,
            before.max_age,
            before.campus_mode,
            before.campus_ids,
            before.exclude_same_department,
        ) != (
            min_age,
            max_age,
            payload.campus_mode,
            campus_ids,
            payload.exclude_same_department,
        )
        if not changed:
            return get_my_preferences(current, db)
        # 하루 3번 제한: 조건을 여러 번 바꿔 보며 상대의 비공개 정보(캠퍼스·학과)를 짐작하는 것을 막는다
        now = utcnow()
        if _window_expired(pref, now):
            pref.change_window_started_at = now
            pref.changes_in_window = 0
        if pref.changes_in_window >= settings.preferences_changes_per_day:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"매칭 조건은 하루에 {settings.preferences_changes_per_day}번까지만 바꿀 수 있어요. 내일 다시 시도해주세요.",
            )
        pref.changes_in_window += 1

    pref.min_age = min_age
    pref.max_age = max_age
    pref.campus_mode = payload.campus_mode
    pref.exclude_same_department = payload.exclude_same_department

    db.query(PreferredCampus).filter(PreferredCampus.user_id == current.id).delete(synchronize_session=False)
    db.add_all([PreferredCampus(user_id=current.id, campus_id=c) for c in campus_ids])
    db.commit()
    return get_my_preferences(current, db)


# ---------- 사진 ----------

def _resubmit_status(db: Session, user_id: uuid.UUID, *, vip: bool = False) -> dict:
    """지금 새 사진을 낼 수 있는지 (2026-09-30 규칙, 2026-10-01 기간 30일 → 7일).

    - 아직 평가를 받은 적 없음(첫 제출, 반려 뒤 다시 내기 등) → 언제든 가능
    - 마지막 평가 후 PHOTO_RESUBMIT_DAYS(7일)가 지남 → 가능
    - 그 안 → "바로 재검토"를 계정당 평생 1번만 쓸 수 있다.
    wait_days: 화면 안내 문구용 (기간을 .env로 바꿔도 문구가 따라 바뀌게)
      바로 재검토로 낸 사진이 승인까지 되면 "사용함"으로 친다.
      (반려되거나, 검수 전에 다른 사진으로 바꾸면 쓴 것으로 치지 않는다)
    vip=True: VIP는 기간이 VIP_PHOTO_RESUBMIT_DAYS(3일)다 (2026-10-02 테스트 계정, 2026-10-03 정식 VIP). 나머지 규칙은 같다.
    """
    settings = get_settings()
    last_eval = (
        db.query(AppearanceEvaluation)
        .filter(AppearanceEvaluation.user_id == user_id)
        .order_by(AppearanceEvaluation.created_at.desc())
        .first()
    )
    free_used = (
        db.query(UserPhoto.id)
        .filter(UserPhoto.user_id == user_id, UserPhoto.free_rereview.is_(True), UserPhoto.review_status == "APPROVED")
        .first()
        is not None
    )
    days = settings.vip_photo_resubmit_days if vip else settings.photo_resubmit_days
    if last_eval is None:
        return {"allowed": True, "uses_free_rereview": False, "free_rereview_left": not free_used, "next_available_at": None, "wait_days": days}
    next_at = as_utc(last_eval.created_at) + timedelta(days=days)
    if utcnow() >= next_at:
        return {"allowed": True, "uses_free_rereview": False, "free_rereview_left": not free_used, "next_available_at": None, "wait_days": days}
    return {
        "wait_days": days,
        "allowed": not free_used,
        "uses_free_rereview": not free_used,
        "free_rereview_left": not free_used,
        "next_available_at": next_at.isoformat(),
    }


@router.post("/me/photos", status_code=status.HTTP_201_CREATED)
def upload_photo(
    background: BackgroundTasks,
    files: list[UploadFile] | None = File(default=None),
    file: UploadFile | None = File(default=None),  # 예전 화면(한 장) 호환
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """사진 제출 (한 번에 1~3장). 함께 낸 사진은 한 묶음으로 함께 검수·평가된다."""
    settings = get_settings()
    uploads = [f for f in (files or []) if f is not None]
    if file is not None:
        uploads.append(file)
    if not uploads:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="사진을 골라주세요.")
    if len(uploads) > settings.photo_max_count:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"사진은 한 번에 {settings.photo_max_count}장까지 올릴 수 있어요.")

    # 첫 이용권 입금이 확인되기 전에는 사진을 받지 않는다 (화면만이 아니라 서버에서 막음, 2026-10-03)
    approved_before = profile_service.has_approved_photo(db, current.id)
    if membership_service.needs_first_payment(current.user, has_approved_photo=approved_before):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="PAYMENT_REQUIRED")
    # 점검 기간에는 기존 회원의 사진 재검토를 받지 않는다 (관리자 일이 몰리지 않게). 새 가입자의 첫 사진은 받는다.
    if approved_before and membership_service.before_open() and not vip_service.is_vip_tester(current.user):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="MAINTENANCE")
    # 이용권이 끝난 사람은 사진 재검토를 신청할 수 없다 (2026-10-04 D9). 첫 검수(반려 후 다시 내기 포함)는 된다.
    if approved_before and not membership_service.has_membership(current.user):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="MEMBERSHIP_REQUIRED")

    enforce_rate_limit(f"photo:{current.id}", 5, 3600)

    rule = _resubmit_status(db, current.id, vip=vip_service.is_vip(current.user))
    if not rule["allowed"]:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"바로 재검토는 이미 한 번 사용했어요. 마지막 평가 후 {rule['wait_days']}일이 지나면 다시 제출할 수 있어요.",
        )

    # 모두 검사를 통과해야 저장한다 (한 장이라도 문제가 있으면 아무것도 저장하지 않음)
    processed = []
    for index, upload in enumerate(uploads, start=1):
        try:
            processed.append(process_upload(upload))
        except PhotoValidationError as exc:
            prefix = f"{index}번째 사진: " if len(uploads) > 1 else ""
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{prefix}{exc}") from exc

    storage = get_storage()
    keys = []
    for item in processed:
        key = new_storage_key(current.id)
        storage.save(key, item.data)
        keys.append(key)

    # 아직 검수 전인 이전 사진(묶음 전체)은 새 사진으로 대체
    db.query(UserPhoto).filter(
        UserPhoto.user_id == current.id, UserPhoto.review_status.in_(["PENDING", "IN_REVIEW"])
    ).update({"review_status": "SUPERSEDED"}, synchronize_session=False)
    submission_id = uuid.uuid4()
    photos = [
        UserPhoto(
            user_id=current.id,
            storage_key=key,
            mime_type=item.mime_type,
            file_size=len(item.data),
            width=item.width,
            height=item.height,
            review_status="PENDING",
            submission_id=submission_id,
            position=position,
            free_rereview=rule["uses_free_rereview"],
        )
        for position, (key, item) in enumerate(zip(keys, processed))
    ]
    db.add_all(photos)
    db.commit()

    # 검수 대기 묶음이 10개 쌓이면 검수 담당 운영진에게 메일 한 통 (응답을 보낸 뒤 발송)
    pending = admin_alert_service.pending_photo_query(db).count()
    if admin_alert_service.photo_backlog_alert_due(pending):
        recipients = admin_alert_service.admin_emails_with(db, "photos:evaluate")
        background.add_task(admin_alert_service.send_all, EmailService.send_admin_photo_queue, recipients, pending)
    return {
        "photo_id": str(photos[0].id),
        "photo_count": len(photos),
        "review_status": "PENDING",
        "used_free_rereview": rule["uses_free_rereview"],
        "message": "관리자 검수 대기 중입니다.",
    }


@router.get("/me/photos")
def list_my_photos(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """사진 검수 상태만 알려준다 (제출 묶음 단위). 원본 사진 주소(storage_key)는 본인에게도 보내지 않는다."""
    leaders = (
        db.query(UserPhoto)
        .filter(UserPhoto.user_id == current.id, UserPhoto.upload_status != "DELETED", UserPhoto.position == 0)
        .order_by(UserPhoto.uploaded_at.desc())
        .limit(10)
        .all()
    )
    counts = dict(
        db.query(UserPhoto.submission_id, func.count(UserPhoto.id))
        .filter(UserPhoto.submission_id.in_([p.submission_id for p in leaders if p.submission_id]))
        .group_by(UserPhoto.submission_id)
        .all()
    )
    return {
        "photos": [
            {
                "photo_id": str(p.id),
                "photo_count": counts.get(p.submission_id, 1),
                "review_status": p.review_status,
                "reject_reason": p.reject_reason,
                "uploaded_at": p.uploaded_at.isoformat(),
                "reviewed_at": p.reviewed_at.isoformat() if p.reviewed_at else None,
            }
            for p in leaders
        ],
        "max_count": get_settings().photo_max_count,
        "resubmit": _resubmit_status(db, current.id, vip=vip_service.is_vip(current.user)),
    }


@router.get("/me/evaluation")
def get_my_evaluation(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """내 외적 평가 점수. 관리자 메모와 평가자 정보는 보내지 않는다."""
    evaluation = profile_service.latest_evaluations(db, [current.id]).get(current.id)
    if evaluation is None:
        return {"evaluated": False}
    return {"evaluated": True, "scores": evaluation.scores(), "evaluated_at": evaluation.created_at.isoformat()}


# ---------- 가입비 (2026-10-03, 운영자 통장 직접 입금) ----------


def _payment_view(payment, *, open_now: bool, required: bool = True) -> dict:
    settings = get_settings()
    show_account = open_now or payment.status == "REQUESTED"
    return {
        "required": required,
        "status": payment.status,  # CREATED / REQUESTED / REJECTED
        "amount": payment.amount,
        "code": payment.code,
        "open_now": open_now,
        "open_hour": settings.payment_open_hour,
        "close_hour": settings.payment_close_hour,
        # 운영 시간 밖에는 계좌번호를 숨긴다 (이미 "입금했어요"를 누른 사람은 그대로 보여줌)
        "bank_name": settings.payment_bank_name if show_account else None,
        "account_number": settings.payment_account_number if show_account else None,
        "account_holder": settings.payment_account_holder if show_account else None,
        "support_email": settings.support_email,
    }


def _request_check(db: Session, background: BackgroundTasks, payment) -> dict:
    """"입금했어요" 공통 처리 (기본 이용권·VIP). 관리자 확인 대기 목록에 올리고 알림 메일을 보낸다."""
    open_now = payment_service.is_payment_open()
    if payment.status == "REQUESTED":
        # 두 번 눌러도 알림 메일은 한 번만
        return _payment_view(payment, open_now=open_now)
    if not open_now:
        settings = get_settings()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"운영 시간 외입니다. 오전 {settings.payment_open_hour}시부터 결제할 수 있어요.",
        )
    enforce_rate_limit(f"payment:{payment.user_id}", 10, 3600)
    payment.status = "REQUESTED"
    payment.requested_at = utcnow()
    db.commit()
    # 15분 이내 확인 약속 → 사진 알림처럼 모으지 않고 요청마다 바로 보낸다 (응답 뒤 발송)
    recipients = admin_alert_service.admin_emails_with(db, "payments:confirm")
    background.add_task(
        admin_alert_service.send_all, EmailService.send_admin_payment_request, recipients, payment.code, payment.amount
    )
    return _payment_view(payment, open_now=open_now)


def _payment_ready(db: Session, current: CurrentUser) -> None:
    """입금 단계는 프로필(학과)과 매칭 조건을 끝낸 뒤에 나온다."""
    if not _profile_done(db, current):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="PROFILE_REQUIRED")
    if db.query(MatchingPreference.id).filter(MatchingPreference.user_id == current.id).first() is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="PREFERENCES_REQUIRED")


def _pays_membership(current: CurrentUser) -> bool:
    """이용권을 살 수 있는(내야 하는) 사람인가. 유료화가 꺼져 있거나 테스트 계정이면 아니다."""
    return membership_service.enabled() and not vip_service.is_vip_tester(current.user)


@router.get("/me/payment")
def get_my_payment(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """기본 이용권(4주) 입금 안내 — 가입 단계의 첫 입금과 연장(언제든, D2)에 같이 쓴다.

    처음 열면 결제 코드가 만들어지고, 다시 열어도 같은 코드가 나온다.
    required: 가입 단계에서 아직 첫 입금을 해야 하는가 (연장일 때는 false).
    """
    if not _pays_membership(current):
        return {"required": False}
    _payment_ready(db, current)
    required = membership_service.needs_first_payment(
        current.user, has_approved_photo=profile_service.has_approved_photo(db, current.id)
    )
    payment = payment_service.get_or_create_payment(db, current.user)
    db.commit()
    return {
        **_payment_view(payment, open_now=payment_service.is_payment_open(), required=required),
        "membership": membership_service.view(current.user),
    }


@router.post("/me/payment/request")
def request_payment_check(
    background: BackgroundTasks,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """"입금했어요". 관리자 확인 대기 목록에 올라가고, 관리자에게 알림 메일이 간다."""
    if not _pays_membership(current):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="지금은 이용권을 판매하지 않아요.")
    _payment_ready(db, current)
    payment = payment_service.get_or_create_payment(db, current.user)
    required = membership_service.needs_first_payment(
        current.user, has_approved_photo=profile_service.has_approved_photo(db, current.id)
    )
    return {**_request_check(db, background, payment), "required": required, "membership": membership_service.view(current.user)}


# ---------- VIP 4주 이용권 (2026-10-03, 2026-10-04 구독제: 기본 포함) ----------


def _vip_info(db: Session, current: CurrentUser) -> dict:
    settings = get_settings()
    user = current.user
    price = vip_service.price()
    info = {
        "visible": vip_service.feature_visible(user),
        "active": vip_service.is_vip(user),
        "tester": vip_service.is_vip_tester(user),
        "until": user.vip_until.isoformat() if vip_service.has_paid_vip(user) else None,
        "days": settings.vip_days,
        "price": price,
        # 지금 남은 기본 이용권 일수 → "VIP를 사면 남은 ○일은 VIP가 끝난 뒤 이어서 써요" 안내
        "member_days_left": membership_service.days_left(user) if membership_service.enabled() else None,
        "daily_like_limit": settings.vip_daily_like_limit,
        "base_like_limit": settings.daily_like_limit,
        "pass_cooldown_hours": settings.vip_pass_cooldown_hours,
        "base_pass_cooldown_hours": settings.pass_cooldown_hours,
        "photo_resubmit_days": settings.vip_photo_resubmit_days,
        "base_photo_resubmit_days": settings.photo_resubmit_days,
        "can_buy": False,
        "blocked_reason": None,
        "payment": None,
    }
    if not settings.vip_enabled:
        # 판매 전 미리 보기 (2026-10-04): 탭은 보이지만 결제 버튼 대신 출시 안내
        info["blocked_reason"] = settings.vip_preview_notice if settings.vip_preview else "VIP는 아직 판매하지 않아요."
    elif vip_service.has_paid_vip(user):
        # VIP가 끝난 뒤에만 다시 살 수 있다 (2026-10-03)
        info["blocked_reason"] = "VIP 기간이 끝난 뒤에 다시 살 수 있어요."
    elif not membership_service.can_start(db, user):
        # 추천이 열려야(승인 사진 + 등급) VIP를 쓸 수 있다. 그 전에 사면 날짜만 줄어든다.
        info["blocked_reason"] = "사진 검수가 끝난 뒤에 VIP를 살 수 있어요."
    else:
        info["can_buy"] = True
        payment = payment_service.get_or_create_payment(db, user, "VIP", price)
        db.commit()
        info["payment"] = _payment_view(payment, open_now=payment_service.is_payment_open())
    return info


@router.get("/me/vip")
def get_my_vip(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """VIP 안내·상태. 살 수 있으면 VIP 결제 코드가 만들어진다 (기본 이용권 코드와 따로)."""
    return _vip_info(db, current)


@router.post("/me/vip/request")
def request_vip_check(
    background: BackgroundTasks,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """VIP "입금했어요". 관리자가 확인하는 순간부터 4주 (기본 포함). 확인 후에는 환불하지 않는다."""
    info = _vip_info(db, current)
    if not info["can_buy"]:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=info["blocked_reason"])
    payment = payment_service.open_payment(db, current.id, "VIP")
    view = _request_check(db, background, payment)
    return {**info, "payment": view}
