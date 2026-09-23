from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.rate_limit import enforce_rate_limit
from app.db.session import get_db
from app.deps import get_current_user
from app.models.matching import Block, Like, Match, Message, Notification, PhotoReview, Report
from app.models.user import User
from app.models.profile import PublicProfile
from app.schemas.matching import BlockRequest, LikeRequest, MatchResponse, ReportRequest, SendMessageRequest

router = APIRouter()


@router.get("/discover")
def discover_profiles(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    blocked_ids = {
        row.blocked_user_id
        for row in db.query(Block).filter(Block.blocker_user_id == current_user["id"]).all()
    }
    blocked_ids.update(
        row.blocker_user_id
        for row in db.query(Block).filter(Block.blocked_user_id == current_user["id"]).all()
    )
    acted_ids = {
        row.to_user_id
        for row in db.query(Like).filter(Like.from_user_id == current_user["id"]).all()
    }
    matched_ids = set()
    for match in db.query(Match).filter(
        (Match.user_a_id == current_user["id"]) | (Match.user_b_id == current_user["id"])
    ).all():
        matched_ids.add(match.user_b_id if str(match.user_a_id) == str(current_user["id"]) else match.user_a_id)

    profiles = (
        db.query(PublicProfile)
        .join(User, PublicProfile.user_id == User.id)
        .join(PhotoReview, PhotoReview.user_id == User.id)
        .filter(User.status == "ACTIVE", PublicProfile.profile_status == "ACTIVE")
        .filter(PhotoReview.status == "APPROVED")
        .distinct()
        .all()
    )
    candidates = []
    for profile in profiles:
        if str(profile.user_id) == str(current_user["id"]):
            continue
        if profile.user_id in blocked_ids or profile.user_id in acted_ids or profile.user_id in matched_ids:
            continue
        candidates.append({
            "id": str(profile.id),
            "user_id": str(profile.user_id),
            "nickname": profile.nickname,
            "campus_id": profile.campus_id,
            "age": profile.age,
            "gender": profile.gender,
            "mbti": profile.mbti,
            "bio": profile.bio,
            "appearance_summary_json": profile.appearance_summary_json,
        })
    return {"profiles": candidates}


@router.post("/blocks")
def block_user(
    payload: BlockRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.blocked_user_id == current_user["id"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="cannot block yourself")
    target = db.query(User).filter(User.id == payload.blocked_user_id).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    existing = db.query(Block).filter(
        Block.blocker_user_id == current_user["id"],
        Block.blocked_user_id == payload.blocked_user_id,
    ).first()
    if not existing:
        db.add(Block(
            blocker_user_id=current_user["id"],
            blocked_user_id=payload.blocked_user_id,
            reason=payload.reason,
        ))
        db.commit()
    return {"blocked": True}


@router.delete("/blocks/{blocked_user_id}")
def unblock_user(
    blocked_user_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    block = db.query(Block).filter(
        Block.blocker_user_id == current_user["id"],
        Block.blocked_user_id == blocked_user_id,
    ).first()
    if not block:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="block not found")
    db.delete(block)
    db.commit()
    return {"unblocked": True}


@router.post("/reports")
def report_user(
    payload: ReportRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enforce_rate_limit(f"report:{current_user['id']}:{request.client.host if request.client else 'unknown'}", 5, 3600)
    if payload.reported_user_id == current_user["id"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="cannot report yourself")
    target = db.query(User).filter(User.id == payload.reported_user_id).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    existing = db.query(Report).filter(
        Report.reporter_user_id == current_user["id"],
        Report.reported_user_id == payload.reported_user_id,
        Report.status.in_(["OPEN", "UNDER_REVIEW"]),
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="report already open")
    report = Report(
        reporter_user_id=current_user["id"],
        reported_user_id=payload.reported_user_id,
        reason=payload.reason,
        description=payload.description,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return {"report_id": str(report.id), "status": report.status}


@router.post("/likes", response_model=MatchResponse)
def like_user(
    payload: LikeRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enforce_rate_limit(f"like:{current_user['id']}", 60, 60)
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


@router.delete("/likes/{to_user_id}")
def pass_user(
    to_user_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if to_user_id == current_user["id"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="cannot pass yourself")
    target = db.query(User).filter(User.id == to_user_id, User.status == "ACTIVE").first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="target user not found")
    like = db.query(Like).filter(
        Like.from_user_id == current_user["id"],
        Like.to_user_id == to_user_id,
    ).first()
    if like:
        like.like_value = False
    else:
        db.add(Like(from_user_id=current_user["id"], to_user_id=to_user_id, like_value=False))
    db.commit()
    return {"passed": True}


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
    if match.status != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="match is not active")
    if match.user_a_id != current_user["id"] and match.user_b_id != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not allowed to access messages")
    if db.query(Block).filter(
        ((Block.blocker_user_id == current_user["id"]) & (Block.blocked_user_id == (match.user_b_id if match.user_a_id == current_user["id"] else match.user_a_id)))
        | ((Block.blocked_user_id == current_user["id"]) & (Block.blocker_user_id == (match.user_b_id if match.user_a_id == current_user["id"] else match.user_a_id)))
    ).first():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="chat is unavailable")
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
    if match.status != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="match is not active")
    if match.user_a_id != current_user["id"] and match.user_b_id != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not allowed to send message")
    other_user_id = match.user_b_id if match.user_a_id == current_user["id"] else match.user_a_id
    if db.query(Block).filter(
        ((Block.blocker_user_id == current_user["id"]) & (Block.blocked_user_id == other_user_id))
        | ((Block.blocked_user_id == current_user["id"]) & (Block.blocker_user_id == other_user_id))
    ).first():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="chat is unavailable")

    message = Message(match_id=match_id, sender_user_id=current_user["id"], body=payload.body)
    db.add(message)
    db.commit()
    return {"match_id": match_id, "message": payload.body, "sent": True}
