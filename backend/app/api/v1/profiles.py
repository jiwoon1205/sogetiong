"""/api/v1/me — 내 계정, 내 공개 프로필, 매칭 조건, 사진, 외적 평가."""

from datetime import timedelta

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.rate_limit import enforce_rate_limit
from app.core.security import verify_password
from app.core.time import as_utc, utcnow
from app.db.session import get_db
from app.deps import CurrentUser, get_current_user
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
from app.services import profile_service
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
            "profile_done": db.query(PublicProfile.id).filter(PublicProfile.user_id == current.id).first() is not None,
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
    card["show_department"] = profile.show_department
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
    if payload.clear_department:
        profile.department_id = None
    elif payload.department_id is not None:
        dept = db.get(Department, payload.department_id)
        # 학과는 내 캠퍼스 소속이어야 한다
        if dept is None or dept.campus_id != profile.campus_id or not dept.active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="학과를 다시 선택해주세요.")
        profile.department_id = dept.id
    if payload.show_department is not None:
        profile.show_department = payload.show_department
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
    return get_my_profile(current, db)


# ---------- 매칭 조건 (Layer 2: 본인만 볼 수 있음) ----------

@router.get("/me/preferences")
def get_my_preferences(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    prefs = profile_service.preferences_of(db, [current.id]).get(current.id)
    if prefs is None:
        return {"configured": False}
    return {
        "configured": True,
        "preferred_gender": prefs.preferred_gender,
        "min_age": prefs.min_age,
        "max_age": prefs.max_age,
        "campus_mode": prefs.campus_mode,
        "campus_ids": sorted(str(i) for i in prefs.campus_ids),
        "excluded_department_ids": sorted(str(i) for i in prefs.excluded_department_ids),
        "preferred_department_ids": sorted(str(i) for i in prefs.preferred_department_ids),
    }


@router.put("/me/preferences")
def put_my_preferences(
    payload: PreferencesRequest,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    if payload.min_age < settings.min_age:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"최소 나이는 {settings.min_age}세 이상이어야 합니다.")

    uni = current.user.university_id
    campus_ids = set(payload.campus_ids)
    if campus_ids:
        valid = {c for (c,) in db.query(Campus.id).filter(Campus.id.in_(campus_ids), Campus.university_id == uni)}
        if valid != campus_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="캠퍼스를 다시 선택해주세요.")
    dept_ids = set(payload.excluded_department_ids) | set(payload.preferred_department_ids)
    if dept_ids:
        valid = {
            d
            for (d,) in db.query(Department.id)
            .join(Campus, Campus.id == Department.campus_id)
            .filter(Department.id.in_(dept_ids), Campus.university_id == uni)
        }
        if valid != dept_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="학과를 다시 선택해주세요.")

    pref = db.query(MatchingPreference).filter(MatchingPreference.user_id == current.id).first()
    if pref is None:
        pref = MatchingPreference(user_id=current.id)
        db.add(pref)
    pref.preferred_gender = payload.preferred_gender
    pref.min_age = payload.min_age
    pref.max_age = payload.max_age
    pref.campus_mode = payload.campus_mode

    for model in (PreferredCampus, ExcludedDepartment, PreferredDepartment):
        db.query(model).filter(model.user_id == current.id).delete(synchronize_session=False)
    if payload.campus_mode == "SELECTED":
        db.add_all([PreferredCampus(user_id=current.id, campus_id=c) for c in campus_ids])
    db.add_all([ExcludedDepartment(user_id=current.id, department_id=d) for d in set(payload.excluded_department_ids)])
    db.add_all([PreferredDepartment(user_id=current.id, department_id=d) for d in set(payload.preferred_department_ids)])
    db.commit()
    return get_my_preferences(current, db)


# ---------- 사진 ----------

@router.post("/me/photos", status_code=status.HTTP_201_CREATED)
def upload_photo(
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
