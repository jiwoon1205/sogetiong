from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user
from app.models.matching import PhotoReview
from app.models.profile import PrivateProfile, PublicProfile
from app.schemas.profile import ProfileUpdateRequest, PublicProfileResponse
from app.services.storage_service import StorageService

router = APIRouter()


@router.get("/me", response_model=PublicProfileResponse)
def get_current_user_profile(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(PublicProfile).filter(PublicProfile.user_id == current_user["id"]).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="profile not found")
    return PublicProfileResponse.model_validate(profile)


@router.patch("/me")
def update_current_user_profile(
    payload: ProfileUpdateRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(PublicProfile).filter(PublicProfile.user_id == current_user["id"]).first()
    if not profile:
        profile = PublicProfile(
            user_id=current_user["id"],
            nickname=payload.nickname or "익명의 대학생",
            bio=payload.bio,
            mbti=payload.mbti,
        )
        db.add(profile)

    if payload.nickname is not None:
        profile.nickname = payload.nickname
    if payload.bio is not None:
        profile.bio = payload.bio
    if payload.mbti is not None:
        profile.mbti = payload.mbti
    if payload.interests is not None:
        profile.ideal_type = ", ".join(payload.interests)

    db.commit()
    db.refresh(profile)
    return {"updated": True, "data": PublicProfileResponse.model_validate(profile).model_dump()}


@router.post("/me/photo")
def upload_profile_photo(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        storage_key = StorageService.save_uploaded_file(file, current_user["id"])
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    private_profile = db.query(PrivateProfile).filter(PrivateProfile.user_id == current_user["id"]).first()
    if not private_profile:
        private_profile = PrivateProfile(user_id=current_user["id"], original_photo_storage_key=storage_key)
        db.add(private_profile)
    else:
        private_profile.original_photo_storage_key = storage_key

    review = PhotoReview(
        user_id=current_user["id"],
        storage_key=storage_key,
        status="PENDING",
    )
    db.add(review)
    db.commit()

    return {
        "stored_path": storage_key,
        "review_id": str(review.id),
        "status": "PENDING",
        "message": "photo saved in private storage and queued for admin review",
    }


@router.get("/profiles/{profile_id}", response_model=PublicProfileResponse)
def get_profile_by_id(profile_id: str, db: Session = Depends(get_db)):
    profile = db.query(PublicProfile).filter(PublicProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="profile not found")
    return PublicProfileResponse.model_validate(profile)
