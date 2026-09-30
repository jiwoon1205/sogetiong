"""/api/v1/me — 내 계정, 내 공개 프로필, 매칭 조건, 사진, 외적 평가."""

from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.rate_limit import enforce_rate_limit
from app.core.security import verify_password
from app.core.time import as_utc, utcnow
from app.db.session import get_db
from app.deps import CurrentUser, get_current_user
# ExcludedDepartment·PreferredDepartment는 베타에서 안 쓰지만, 탈퇴할 때 예전 데이터를 지우는 데 쓴다
from app.models.matching import (
    ExcludedDepartment,
    Match,
    MatchingPreference,
    PreferredCampus,
    PreferredDepartment,
)
from app.models.photo import AppearanceEvaluation, UserPhoto
from app.models.profile import Interest, PublicProfile, UserInterest
from app.models.university import Campus, Department
from app.schemas.auth import DeleteAccountRequest
from app.schemas.profile import PreferencesRequest, ProfileUpdateRequest
from app.services import admin_alert_service, auth_service, profile_service
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
        },
    }


@router.delete("/me")
def delete_me(
    payload: DeleteAccountRequest,
    response: Response,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """회원 탈퇴 (설계도 §45).

    즉시 삭제: 공개 프로필, 관심사, 매칭 조건, 사진 파일, 로그인 세션
    익명화: 이메일 → 가짜 주소 + 지문(email_hash)만 보관 (재가입 허용, 정지 이력·차단 관계 확인용)
    보존(법률 검토 후 보유기간 확정): 계정 기본정보, private profile, 신고·채팅 기록
    TODO(법률 검토): 보유기간이 지나면 자동 파기하는 작업 추가
    """
    if not verify_password(payload.password, current.user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="비밀번호가 올바르지 않습니다.")

    uid = current.id
    storage = get_storage()
    for photo in db.query(UserPhoto).filter(UserPhoto.user_id == uid):
        if photo.storage_key:
            storage.delete(photo.storage_key)
        photo.storage_key = ""
        photo.upload_status = "DELETED"
    for model in (UserInterest, PreferredCampus, ExcludedDepartment, PreferredDepartment, MatchingPreference, PublicProfile):
        db.query(model).filter(model.user_id == uid).delete(synchronize_session=False)
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
    return pref.change_window_started_at is None or now - as_utc(pref.change_window_started_at) >= timedelta(days=1)


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

@router.post("/me/photos", status_code=status.HTTP_201_CREATED)
def upload_photo(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    enforce_rate_limit(f"photo:{current.id}", 5, 3600)

    # 재평가는 마지막 평가 후 일정 기간이 지나야 요청할 수 있다
    last_eval = (
        db.query(AppearanceEvaluation)
        .filter(AppearanceEvaluation.user_id == current.id)
        .order_by(AppearanceEvaluation.created_at.desc())
        .first()
    )
    if last_eval and utcnow() - as_utc(last_eval.created_at) < timedelta(days=settings.photo_resubmit_days):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"사진 재평가는 {settings.photo_resubmit_days}일에 한 번만 요청할 수 있습니다.",
        )

    try:
        processed = process_upload(file)
    except PhotoValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    key = new_storage_key(current.id)
    get_storage().save(key, processed.data)

    # 아직 검수 전인 이전 사진은 새 사진으로 대체
    db.query(UserPhoto).filter(
        UserPhoto.user_id == current.id, UserPhoto.review_status.in_(["PENDING", "IN_REVIEW"])
    ).update({"review_status": "SUPERSEDED"}, synchronize_session=False)
    photo = UserPhoto(
        user_id=current.id,
        storage_key=key,
        mime_type=processed.mime_type,
        file_size=len(processed.data),
        width=processed.width,
        height=processed.height,
        review_status="PENDING",
    )
    db.add(photo)
    db.commit()

    # 검수 대기 사진이 10장 쌓이면 검수 담당 운영진에게 메일 한 통 (응답을 보낸 뒤 발송)
    pending = admin_alert_service.pending_photo_query(db).count()
    if admin_alert_service.photo_backlog_alert_due(pending):
        recipients = admin_alert_service.admin_emails_with(db, "photos:evaluate")
        background.add_task(admin_alert_service.send_all, EmailService.send_admin_photo_queue, recipients, pending)
    return {"photo_id": str(photo.id), "review_status": photo.review_status, "message": "관리자 검수 대기 중입니다."}


@router.get("/me/photos")
def list_my_photos(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """사진 검수 상태만 알려준다. 원본 사진 주소(storage_key)는 본인에게도 보내지 않는다."""
    photos = (
        db.query(UserPhoto)
        .filter(UserPhoto.user_id == current.id, UserPhoto.upload_status != "DELETED")
        .order_by(UserPhoto.uploaded_at.desc())
        .limit(10)
        .all()
    )
    return {
        "photos": [
            {
                "photo_id": str(p.id),
                "review_status": p.review_status,
                "reject_reason": p.reject_reason,
                "uploaded_at": p.uploaded_at.isoformat(),
                "reviewed_at": p.reviewed_at.isoformat() if p.reviewed_at else None,
            }
            for p in photos
        ]
    }


@router.get("/me/evaluation")
def get_my_evaluation(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """내 외적 평가 점수. 관리자 메모와 평가자 정보는 보내지 않는다."""
    evaluation = profile_service.latest_evaluations(db, [current.id]).get(current.id)
    if evaluation is None:
        return {"evaluated": False}
    return {"evaluated": True, "scores": evaluation.scores(), "evaluated_at": evaluation.created_at.isoformat()}
