from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.profile import ProfileUpdateRequest, PublicProfileResponse

router = APIRouter()


@router.get("/me", response_model=PublicProfileResponse)
def get_current_user_profile(db: Session = Depends(get_db)):
    return PublicProfileResponse(
        id="demo-user-id",
        nickname="익명의 대학생",
        campus_id="campus-1",
        age=21,
        gender="female",
        mbti="INTP",
        bio="카페와 영화를 좋아합니다.",
    )


@router.patch("/me")
def update_current_user_profile(payload: ProfileUpdateRequest, db: Session = Depends(get_db)):
    return {"updated": True, "data": payload.model_dump(exclude_none=True)}


@router.get("/profiles/{profile_id}", response_model=PublicProfileResponse)
def get_profile_by_id(profile_id: str, db: Session = Depends(get_db)):
    if profile_id == "missing":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="profile not found")
    return PublicProfileResponse(
        id=profile_id,
        nickname="익명의 대학생",
        campus_id="campus-1",
        age=22,
        gender="male",
        mbti="ENFP",
        bio="대화를 좋아합니다.",
    )
