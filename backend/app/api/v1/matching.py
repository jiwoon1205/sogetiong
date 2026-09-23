from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.matching import LikeRequest, MatchResponse, SendMessageRequest

router = APIRouter()


@router.post("/likes", response_model=MatchResponse)
def like_user(payload: LikeRequest, db: Session = Depends(get_db)):
    return MatchResponse(liked=True, matched=False)


@router.get("/matches")
def list_matches(db: Session = Depends(get_db)):
    return {"matches": []}


@router.get("/matches/{match_id}")
def get_match(match_id: str, db: Session = Depends(get_db)):
    return {"match_id": match_id, "status": "ACTIVE"}


@router.get("/matches/{match_id}/messages")
def get_messages(match_id: str, db: Session = Depends(get_db)):
    return {"match_id": match_id, "messages": []}


@router.post("/matches/{match_id}/messages")
def send_message(match_id: str, payload: SendMessageRequest, db: Session = Depends(get_db)):
    return {"match_id": match_id, "message": payload.body, "sent": True}
