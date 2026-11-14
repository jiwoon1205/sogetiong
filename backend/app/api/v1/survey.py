"""사용자 설문 (2026-10-05, 2026-11-14 새 설문). 규칙은 app/services/survey_service.py 맨 위 설명.

- router       → /api/v1/me/survey        (사용자)
- admin_router → /api/v1/admin/survey     (관리자: 켜기/끄기, 결과 보기)
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import CurrentAdmin, CurrentUser, get_current_user, require_permission
from app.models.profile import PublicProfile
from app.models.survey import SurveyResponse
from app.models.user import User
from app.schemas.survey import SurveyAnswerRequest, SurveyOpenRequest
from app.services import audit_service, survey_service

router = APIRouter()
admin_router = APIRouter()

# ---------- 사용자 ----------

@router.get("/me/survey")
def get_my_survey(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return {
        "open": survey_service.is_open(db),
        "answered": survey_service.has_answered(db, current.id),
        "pending": survey_service.pending(db, current.id),
    }


@router.post("/me/survey", status_code=status.HTTP_201_CREATED)
def answer_survey(
    payload: SurveyAnswerRequest,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not survey_service.is_open(db):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="지금은 설문을 받고 있지 않아요.")
    if survey_service.has_answered(db, current.id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 설문에 참여했어요. 감사합니다!")
    db.add(
        SurveyResponse(
            user_id=current.id,
            survey_key=survey_service.SURVEY_KEY,
            improvement=payload.improvement,
            feature_request=payload.feature_request,
        )
    )
    try:
        db.commit()
    except IntegrityError:  # 버튼을 두 번 빠르게 눌러 거의 동시에 들어온 경우
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 설문에 참여했어요. 감사합니다!")
    return {"ok": True}


# ---------- 관리자 ----------

def _genders(db: Session, user_ids: list) -> dict:
    """응답자 성별 (분석용). 탈퇴해서 프로필이 지워진 사람은 탈퇴할 때 남긴 성별."""
    if not user_ids:
        return {}
    result = {uid: g for uid, g in db.query(PublicProfile.user_id, PublicProfile.gender).filter(PublicProfile.user_id.in_(user_ids))}
    for uid, g in db.query(User.id, User.deleted_gender).filter(User.id.in_(user_ids)):
        if uid not in result and g:
            result[uid] = g
    return result


@admin_router.get("/survey")
def survey_results(
    admin: CurrentAdmin = Depends(require_permission("surveys:manage")),
    db: Session = Depends(get_db),
):
    """설문 결과 (2026-11-14 새 설문). 닉네임·이메일은 보여주지 않는다 (성별만)."""
    rows = (
        db.query(SurveyResponse)
        .filter(SurveyResponse.survey_key == survey_service.SURVEY_KEY)
        .order_by(SurveyResponse.created_at.desc())
        .all()
    )
    genders = _genders(db, [r.user_id for r in rows])
    written = [r for r in rows if r.improvement or r.feature_request]
    return {
        "open": survey_service.is_open(db),
        "total": len(rows),
        "by_gender": {
            "MALE": sum(1 for r in rows if genders.get(r.user_id) == "MALE"),
            "FEMALE": sum(1 for r in rows if genders.get(r.user_id) == "FEMALE"),
        },
        "written": len(written),
        "skipped": len(rows) - len(written),
        # 글을 적은 응답만 (건너뛴 사람은 숫자로만)
        "responses": [
            {
                "id": str(r.id),
                "gender": genders.get(r.user_id),
                "improvement": r.improvement,
                "feature_request": r.feature_request,
                "created_at": r.created_at.isoformat(),
            }
            for r in written
        ],
    }


@admin_router.put("/survey/open")
def set_survey_open(
    payload: SurveyOpenRequest,
    request: Request,
    admin: CurrentAdmin = Depends(require_permission("surveys:manage")),
    db: Session = Depends(get_db),
):
    before = survey_service.is_open(db)
    survey_service.set_open(db, payload.open)
    audit_service.record(
        db,
        admin_id=admin.id,
        action="SURVEY_OPEN" if payload.open else "SURVEY_CLOSE",
        target_type="SURVEY",
        target_id=survey_service.SURVEY_KEY,
        request=request,
        metadata={"before": before, "after": payload.open},
    )
    db.commit()
    return {"open": payload.open}
