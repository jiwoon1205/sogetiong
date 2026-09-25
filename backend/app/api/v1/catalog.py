"""/api/v1 — 학교·캠퍼스·학과·관심사 목록 (가입 화면에서 쓰므로 로그인 불필요)."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.profile import Interest
from app.models.university import Campus, Department, University

router = APIRouter()


@router.get("/universities")
def list_universities(db: Session = Depends(get_db)):
    rows = db.query(University).filter(University.active.is_(True)).order_by(University.name).all()
    return {"universities": [{"id": str(u.id), "name": u.name, "email_domain": u.email_domain} for u in rows]}


@router.get("/universities/{university_id}/campuses")
def list_campuses(university_id: uuid.UUID, db: Session = Depends(get_db)):
    rows = (
        db.query(Campus)
        .filter(Campus.university_id == university_id, Campus.active.is_(True))
        .order_by(Campus.name)
        .all()
    )
    return {"campuses": [{"id": str(c.id), "name": c.name} for c in rows]}


@router.get("/campuses/{campus_id}/departments")
def list_departments(campus_id: uuid.UUID, db: Session = Depends(get_db)):
    rows = (
        db.query(Department)
        .filter(Department.campus_id == campus_id, Department.active.is_(True))
        .order_by(Department.name)
        .all()
    )
    return {"departments": [{"id": str(d.id), "name": d.name} for d in rows]}


@router.get("/interests")
def list_interests(db: Session = Depends(get_db)):
    return {"interests": [i.name for i in db.query(Interest).order_by(Interest.name).all()]}
