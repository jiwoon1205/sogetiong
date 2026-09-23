from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_admin, require_role
from app.models.matching import AppearanceEvaluation, PhotoReview, Report
from app.models.profile import PublicProfile
from app.schemas.admin import PhotoReviewRequest
from app.services.storage_service import StorageService
from app.services.audit_service import AuditService

router = APIRouter()


@router.get("/users")
def list_users(current_user: dict = Depends(get_current_admin), db: Session = Depends(get_db)):
    require_role(current_user, {"SUPER_ADMIN", "MODERATOR"})
    return {"users": []}


@router.get("/photo-reviews")
def list_photo_reviews(current_user: dict = Depends(get_current_admin), db: Session = Depends(get_db)):
    require_role(current_user, {"SUPER_ADMIN", "PHOTO_REVIEWER"})
    reviews = db.query(PhotoReview).order_by(PhotoReview.created_at.desc()).all()
    return {
        "reviews": [
            {
                "id": str(review.id),
                "user_id": str(review.user_id),
                "status": review.status,
                "review_version": review.review_version,
            }
            for review in reviews
        ]
    }


@router.get("/photo-reviews/{review_id}")
def get_photo_review(review_id: str, current_user: dict = Depends(get_current_admin), db: Session = Depends(get_db)):
    require_role(current_user, {"SUPER_ADMIN", "PHOTO_REVIEWER"})
    review = db.query(PhotoReview).filter(PhotoReview.id == review_id).first()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="photo review not found")
    return {
        "review_id": review_id,
        "user_id": str(review.user_id),
        "status": review.status,
    }


@router.get("/photo-reviews/{review_id}/image")
def get_photo_review_image(
    review_id: str,
    current_user: dict = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    require_role(current_user, {"SUPER_ADMIN", "PHOTO_REVIEWER"})
    review = db.query(PhotoReview).filter(PhotoReview.id == review_id).first()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="photo review not found")

    file_path = StorageService.STORAGE_ROOT / review.storage_key
    if not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="photo file not found")

    AuditService.record(
        db,
        admin_id=current_user["id"],
        action="PHOTO_VIEW",
        target_type="PHOTO_REVIEW",
        target_id=review_id,
    )
    db.commit()
    return FileResponse(file_path)


@router.post("/photo-reviews/{review_id}/review")
def review_photo(
    review_id: str,
    payload: PhotoReviewRequest,
    current_user: dict = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    require_role(current_user, {"SUPER_ADMIN", "PHOTO_REVIEWER"})
    review = db.query(PhotoReview).filter(PhotoReview.id == review_id).first()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="photo review not found")

    decision = payload.decision.upper()
    if decision not in {"APPROVED", "REJECTED", "PENDING"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid review decision")

    scores = {
        "overall_impression": payload.overall_impression,
        "style": payload.style,
        "grooming": payload.grooming,
        "photo_vibe": payload.photo_vibe,
    }
    if decision == "APPROVED" and any(score is None for score in scores.values()):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="all appearance scores are required")

    review.status = decision
    review.reviewed_by_admin_id = current_user["id"]
    review.reviewed_at = __import__("datetime").datetime.utcnow()
    AuditService.record(
        db,
        admin_id=current_user["id"],
        action="PHOTO_REVIEW",
        target_type="PHOTO_REVIEW",
        target_id=review_id,
        metadata={"decision": decision},
    )

    if decision == "APPROVED":
        evaluation = AppearanceEvaluation(
            user_id=review.user_id,
            overall_impression=payload.overall_impression,
            style=payload.style,
            grooming=payload.grooming,
            photo_vibe=payload.photo_vibe,
            evaluator_admin_id=current_user["id"],
            evaluation_note=payload.note,
        )
        db.add(evaluation)

        profile = db.query(PublicProfile).filter(PublicProfile.user_id == review.user_id).first()
        if profile:
            profile.appearance_summary_json = {
                "overall_impression": payload.overall_impression,
                "style": payload.style,
                "grooming": payload.grooming,
                "photo_vibe": payload.photo_vibe,
            }
    db.commit()
    return {
        "review_id": review_id,
        "status": review.status,
        "reviewed_by": current_user["id"],
        "appearance_summary": scores if decision == "APPROVED" else None,
    }


@router.get("/reports")
def list_reports(current_user: dict = Depends(get_current_admin), db: Session = Depends(get_db)):
    require_role(current_user, {"SUPER_ADMIN", "MODERATOR"})
    reports = db.query(Report).order_by(Report.created_at.desc()).all()
    return {
        "reports": [
            {
                "id": str(report.id),
                "reporter_user_id": str(report.reporter_user_id),
                "reported_user_id": str(report.reported_user_id),
                "reason": report.reason,
                "description": report.description,
                "status": report.status,
            }
            for report in reports
        ]
    }


@router.patch("/reports/{report_id}")
def resolve_report(report_id: str, current_user: dict = Depends(get_current_admin), db: Session = Depends(get_db)):
    require_role(current_user, {"SUPER_ADMIN", "MODERATOR"})
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="report not found")
    report.status = "RESOLVED"
    report.reviewed_by_admin_id = current_user["id"]
    report.resolved_at = __import__("datetime").datetime.utcnow()
    AuditService.record(
        db,
        admin_id=current_user["id"],
        action="REPORT_RESOLVE",
        target_type="REPORT",
        target_id=report_id,
        metadata={"status": report.status},
    )
    db.commit()
    return {"report_id": report_id, "status": report.status}
