from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user, require_admin

router = APIRouter()


@router.get("/users")
def list_users(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    require_admin(current_user)
    return {"users": []}


@router.get("/photo-reviews")
def list_photo_reviews(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    require_admin(current_user)
    return {"reviews": []}


@router.get("/photo-reviews/{review_id}")
def get_photo_review(review_id: str, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    require_admin(current_user)
    return {"review_id": review_id, "status": "PENDING"}


@router.get("/reports")
def list_reports(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    require_admin(current_user)
    return {"reports": []}


@router.patch("/reports/{report_id}")
def resolve_report(report_id: str, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    require_admin(current_user)
    return {"report_id": report_id, "status": "RESOLVED"}
