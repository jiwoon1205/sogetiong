from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user
from app.models.matching import Like, Match, Message
from app.schemas.matching import LikeRequest, MatchResponse, SendMessageRequest

router = APIRouter()


@router.post("/likes", response_model=MatchResponse)
def like_user(
    payload: LikeRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.to_user_id == current_user["id"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="cannot like yourself")

    like_record = Like(
        from_user_id=current_user["id"],
        to_user_id=payload.to_user_id,
        like_value=True,
    )
    db.add(like_record)
    db.commit()

    reverse_like = (
        db.query(Like)
        .filter(
            Like.from_user_id == payload.to_user_id,
            Like.to_user_id == current_user["id"],
            Like.like_value.is_(True),
        )
        .first()
    )

    matched = reverse_like is not None
    if matched:
        match_pair = sorted([current_user["id"], payload.to_user_id])
        existing_match = (
            db.query(Match)
            .filter(
                Match.user_a_id == match_pair[0],
                Match.user_b_id == match_pair[1],
            )
            .first()
        )
        if not existing_match:
            match = Match(user_a_id=match_pair[0], user_b_id=match_pair[1], status="ACTIVE")
            db.add(match)
            db.commit()

    return MatchResponse(liked=True, matched=matched)


@router.get("/matches")
def list_matches(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    matches = db.query(Match).filter((Match.user_a_id == current_user["id"]) | (Match.user_b_id == current_user["id"])).all()
    return {"matches": [{"id": str(match.id), "user_a_id": str(match.user_a_id), "user_b_id": str(match.user_b_id), "status": match.status} for match in matches]}


@router.get("/matches/{match_id}")
def get_match(match_id: str, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="match not found")
    if match.user_a_id != current_user["id"] and match.user_b_id != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not allowed to access match")
    return {"match_id": match_id, "status": match.status}


@router.get("/matches/{match_id}/messages")
def get_messages(match_id: str, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="match not found")
    if match.user_a_id != current_user["id"] and match.user_b_id != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not allowed to access messages")
    messages = db.query(Message).filter(Message.match_id == match_id).order_by(Message.created_at.asc()).all()
    return {"match_id": match_id, "messages": [{"id": str(msg.id), "body": msg.body, "sender_user_id": str(msg.sender_user_id)} for msg in messages]}


@router.post("/matches/{match_id}/messages")
def send_message(
    match_id: str,
    payload: SendMessageRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="match not found")
    if match.user_a_id != current_user["id"] and match.user_b_id != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not allowed to send message")

    message = Message(match_id=match_id, sender_user_id=current_user["id"], body=payload.body)
    db.add(message)
    db.commit()
    return {"match_id": match_id, "message": payload.body, "sent": True}
