from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user, require_admin
from app.models.matching import PhotoReview

router = APIRouter()


@router.get("/users")
def list_users(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    require_admin(current_user)
    return {"users": []}


@router.get("/photo-reviews")
def list_photo_reviews(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    require_admin(current_user)
    reviews = db.query(PhotoReview).order_by(PhotoReview.created_at.desc()).all()
    return {
        "reviews": [
            {
                "id": str(review.id),
                "user_id": str(review.user_id),
                "status": review.status,
                "review_version": review.review_version,
                "storage_key": review.storage_key,
            }
            for review in reviews
        ]
    }


@router.get("/photo-reviews/{review_id}")
def get_photo_review(review_id: str, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    require_admin(current_user)
    review = db.query(PhotoReview).filter(PhotoReview.id == review_id).first()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="photo review not found")
    return {
        "review_id": review_id,
        "user_id": str(review.user_id),
        "status": review.status,
        "storage_key": review.storage_key,
    }


@router.post("/photo-reviews/{review_id}/review")
def review_photo(
    review_id: str,
    payload: dict,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)
    review = db.query(PhotoReview).filter(PhotoReview.id == review_id).first()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="photo review not found")

    decision = payload.get("decision", "APPROVED").upper()
    if decision not in {"APPROVED", "REJECTED", "PENDING"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid review decision")

    review.status = decision
    review.reviewed_by_admin_id = current_user["id"]
    db.commit()
    return {"review_id": review_id, "status": review.status, "reviewed_by": current_user["id"]}


@router.get("/reports")
def list_reports(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    require_admin(current_user)
    return {"reports": []}


@router.patch("/reports/{report_id}")
def resolve_report(report_id: str, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    require_admin(current_user)
    return {"report_id": report_id, "status": "RESOLVED"}
