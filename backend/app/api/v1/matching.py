from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user
from app.models.matching import Block, Like, Match, Message, Notification
from app.models.user import User
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

    target_user = db.query(User).filter(User.id == payload.to_user_id, User.status == "ACTIVE").first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="target user not found")

    blocked = db.query(Block).filter(
        ((Block.blocker_user_id == current_user["id"]) & (Block.blocked_user_id == payload.to_user_id))
        | ((Block.blocker_user_id == payload.to_user_id) & (Block.blocked_user_id == current_user["id"]))
    ).first()
    if blocked:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user is blocked")

    like_record = db.query(Like).filter(
        Like.from_user_id == current_user["id"],
        Like.to_user_id == payload.to_user_id,
    ).first()
    if like_record:
        like_record.like_value = True
    else:
        db.add(Like(from_user_id=current_user["id"], to_user_id=payload.to_user_id, like_value=True))
    db.flush()

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
    match = None
    if matched:
        match_pair = sorted([current_user["id"], payload.to_user_id])
        match = (
            db.query(Match)
            .filter(
                Match.user_a_id == match_pair[0],
                Match.user_b_id == match_pair[1],
            )
            .first()
        )
        if not match:
            match = Match(user_a_id=match_pair[0], user_b_id=match_pair[1], status="ACTIVE")
            db.add(match)
            db.flush()
            db.add_all([
                Notification(
                    user_id=current_user["id"],
                    type="MATCH_CREATED",
                    title="새로운 매칭이 생겼어요",
                    body="서로 좋아요를 보내 매칭되었습니다. 이제 대화를 시작해보세요.",
                ),
                Notification(
                    user_id=payload.to_user_id,
                    type="MATCH_CREATED",
                    title="새로운 매칭이 생겼어요",
                    body="서로 좋아요를 보내 매칭되었습니다. 이제 대화를 시작해보세요.",
                ),
            ])
    db.commit()

    match_id = str(match.id) if match else None
    return MatchResponse(liked=True, matched=matched, match_id=match_id, chat_room_id=match_id)


@router.get("/matches")
def list_matches(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    matches = db.query(Match).filter((Match.user_a_id == current_user["id"]) | (Match.user_b_id == current_user["id"])).all()
    return {
        "matches": [
            {
                "id": str(match.id),
                "chat_room_id": str(match.id),
                "user_a_id": str(match.user_a_id),
                "user_b_id": str(match.user_b_id),
                "status": match.status,
            }
            for match in matches
        ]
    }


@router.get("/matches/{match_id}")
def get_match(match_id: str, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="match not found")
    if match.user_a_id != current_user["id"] and match.user_b_id != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not allowed to access match")
    return {"match_id": match_id, "chat_room_id": match_id, "status": match.status}


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
