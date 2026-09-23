from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter()


@router.get("/users")
def list_users(db: Session = Depends(get_db)):
    return {"users": []}


@router.get("/photo-reviews")
def list_photo_reviews(db: Session = Depends(get_db)):
    return {"reviews": []}


@router.get("/photo-reviews/{review_id}")
def get_photo_review(review_id: str, db: Session = Depends(get_db)):
    return {"review_id": review_id, "status": "PENDING"}


@router.get("/reports")
def list_reports(db: Session = Depends(get_db)):
    return {"reports": []}


@router.patch("/reports/{report_id}")
def resolve_report(report_id: str, db: Session = Depends(get_db)):
    return {"report_id": report_id, "status": "RESOLVED"}
