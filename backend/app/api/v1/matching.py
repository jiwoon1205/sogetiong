"""/api/v1 — 추천(discover), LIKE/PASS, 매칭, 채팅."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.rate_limit import enforce_rate_limit
from app.core.time import utcnow
from app.db.session import get_db
from app.deps import CurrentUser, get_current_user
from app.models.matching import Like, Match, MatchingPreference, Message
from app.models.profile import PublicProfile
from app.models.user import User
from app.schemas.matching import SendMessageRequest, TargetRequest
from app.services import matching_service, profile_service
from app.services.notification_service import has_unread, notify

router = APIRouter()


def _viewer(db: Session, current: CurrentUser) -> matching_service.Person:
    """추천을 받으려면 공개 프로필(학과 포함)과 매칭 조건이 있어야 하고, (설정에 따라) 사진이 승인돼 있어야 한다."""
    profile = db.query(PublicProfile).filter(PublicProfile.user_id == current.id).first()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="PROFILE_REQUIRED")
    # 학과는 필수: 학과가 없으면 추천도 LIKE도 할 수 없다 (매칭 엔진에서도 한 번 더 거른다)
    if profile.department_id is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="DEPARTMENT_REQUIRED")
    if db.query(MatchingPreference.id).filter(MatchingPreference.user_id == current.id).first() is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="PREFERENCES_REQUIRED")
    if get_settings().require_approved_photo_to_discover and not profile_service.has_approved_photo(db, current.id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="PHOTO_APPROVAL_REQUIRED")
    return profile_service.people_from_profiles(db, [profile])[0]


# ---------- 추천 ----------

@router.get("/discover")
def discover(
    limit: int | None = Query(default=None, ge=1, le=20),
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enforce_rate_limit(f"discover:{current.id}", 60, 60)
    viewer = _viewer(db, current)
    excluded = profile_service.excluded_user_ids(db, current.id)

    query = profile_service.discoverable_profiles_query(db, current.user.university_id).filter(
        PublicProfile.user_id.notin_(excluded)
    )
    # 성별은 DB에서 먼저 거르고(빠름), 나머지 조건은 매칭 엔진에서 양방향으로 확인
    if viewer.preferences and viewer.preferences.preferred_gender != "ANY":
        query = query.filter(PublicProfile.gender == viewer.preferences.preferred_gender)
    profiles = query.all()

    by_user = {p.user_id: p for p in profiles}
    ranked = matching_service.rank(
        viewer,
        profile_service.people_from_profiles(db, profiles),
        profile_service.matching_weights(),
        limit or get_settings().discover_page_size,
    )
    cards = profile_service.build_cards(db, [by_user[p.user_id] for p in ranked])
    # 후보가 없을 때 조건을 자동으로 넓히지 않는다 (설계도 §56, §57)
    return {"profiles": cards, "empty": not cards}


# ---------- LIKE / PASS ----------

def _target(db: Session, current: CurrentUser, profile_id: uuid.UUID) -> PublicProfile:
    target = profile_service.find_active_profile(db, profile_id)
    if target is None or target.user_id == current.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="프로필을 찾을 수 없습니다.")
    return target


def _upsert_action(db: Session, from_id: uuid.UUID, to_id: uuid.UUID, action: str) -> None:
    row = db.query(Like).filter(Like.from_user_id == from_id, Like.to_user_id == to_id).first()
    if row:
        row.action = action
    else:
        db.add(Like(from_user_id=from_id, to_user_id=to_id, action=action))


@router.post("/likes")
def like(payload: TargetRequest, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    enforce_rate_limit(f"like:{current.id}", 60, 60)
    enforce_rate_limit(f"like-daily:{current.id}", 300, 86400)
    target = _target(db, current, payload.profile_id)
    viewer = _viewer(db, current)

    # ID를 직접 넣어도, 추천 조건에 맞지 않는 사람에게는 LIKE할 수 없다 (설계도 금지사항 #18)
    if target.user_id in profile_service.excluded_user_ids(db, current.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="프로필을 찾을 수 없습니다.")
    candidates = profile_service.people_from_profiles(db, [target])
    if not candidates or not matching_service.mutually_compatible(viewer, candidates[0]):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="프로필을 찾을 수 없습니다.")

    _upsert_action(db, current.id, target.user_id, "LIKE")
    db.flush()

    reverse = (
        db.query(Like)
        .filter(Like.from_user_id == target.user_id, Like.to_user_id == current.id, Like.action == "LIKE")
        .first()
    )
    match = None
    if reverse:
        a, b = profile_service.match_pair(current.id, target.user_id)
        match = Match(user_a_id=a, user_b_id=b, status="ACTIVE")
        db.add(match)
        db.flush()
        for uid in (a, b):
            notify(db, uid, "MATCH_CREATED", "새로운 매칭이 생겼어요", "서로 LIKE를 보내 매칭되었습니다. 대화를 시작해보세요.", match.id)
    try:
        db.commit()
    except IntegrityError:
        # 두 사람이 거의 동시에 LIKE한 경우: 이미 만들어진 매칭을 사용
        db.rollback()
        a, b = profile_service.match_pair(current.id, target.user_id)
        match = db.query(Match).filter(Match.user_a_id == a, Match.user_b_id == b).first()

    # 매칭되기 전에는 상대가 나를 LIKE했는지 알려주지 않는다 (설계도 §23)
    return {"matched": match is not None, "match_id": str(match.id) if match else None}


@router.post("/passes")
def pass_profile(payload: TargetRequest, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    enforce_rate_limit(f"pass:{current.id}", 120, 60)
    target = _target(db, current, payload.profile_id)
    _upsert_action(db, current.id, target.user_id, "PASS")
    db.commit()
    return {"passed": True}


@router.delete("/passes/{profile_id}")
def undo_pass(profile_id: uuid.UUID, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """PASS 취소 (향후 Undo 기능용, 설계도 §21)."""
    target = _target(db, current, profile_id)
    row = db.query(Like).filter(Like.from_user_id == current.id, Like.to_user_id == target.user_id, Like.action == "PASS").first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PASS 기록이 없습니다.")
    db.delete(row)
    db.commit()
    return {"undone": True}


# ---------- 매칭 ----------

def _my_match(db: Session, current: CurrentUser, match_id: uuid.UUID, *, require_active: bool = True) -> Match:
    """내가 속한 매칭만 조회. 남의 매칭이면 존재 여부도 알려주지 않도록 404."""
    match = db.get(Match, match_id)
    if match is None or not match.has_member(current.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="대화방을 찾을 수 없습니다.")
    if require_active:
        partner = match.partner_of(current.id)
        partner_user = db.get(User, partner)
        if (
            match.status != "ACTIVE"
            or partner_user is None
            or partner_user.status != "ACTIVE"
            or profile_service.is_blocked_between(db, current.id, partner)
        ):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="더 이상 대화할 수 없는 상대입니다.")
    return match


def _partner_cards(db: Session, matches: list[Match], me: uuid.UUID) -> dict[uuid.UUID, dict]:
    partner_ids = [m.partner_of(me) for m in matches]
    profiles = db.query(PublicProfile).filter(PublicProfile.user_id.in_(partner_ids)).all() if partner_ids else []
    cards = profile_service.build_cards(db, profiles)
    return {p.user_id: card for p, card in zip(profiles, cards)}


@router.get("/matches")
def list_matches(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    matches = (
        db.query(Match)
        .filter(((Match.user_a_id == current.id) | (Match.user_b_id == current.id)) & (Match.status == "ACTIVE"))
        .order_by(Match.created_at.desc())
        .all()
    )
    cards = _partner_cards(db, matches, current.id)
    result = []
    for m in matches:
        partner = m.partner_of(current.id)
        if partner not in cards or profile_service.is_blocked_between(db, current.id, partner):
            continue
        last = db.query(Message).filter(Message.match_id == m.id).order_by(Message.created_at.desc()).first()
        result.append(
            {
                "match_id": str(m.id),
                "matched_at": m.created_at.isoformat(),
                "partner": cards[partner],
                "last_message": {
                    "body": last.body,
                    "is_mine": last.sender_user_id == current.id,
                    "sent_at": last.created_at.isoformat(),
                }
                if last
                else None,
            }
        )
    return {"matches": result}


@router.get("/matches/{match_id}")
def get_match(match_id: uuid.UUID, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    match = _my_match(db, current, match_id)
    cards = _partner_cards(db, [match], current.id)
    return {
        "match_id": str(match.id),
        "status": match.status,
        "matched_at": match.created_at.isoformat(),
        "partner": cards.get(match.partner_of(current.id)),
    }


@router.delete("/matches/{match_id}")
def unmatch(match_id: uuid.UUID, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """매칭 해제. 해제된 상대는 다시 추천되지 않는다."""
    match = _my_match(db, current, match_id, require_active=False)
    if match.status == "ACTIVE":
        match.status = "UNMATCHED"
        match.ended_at = utcnow()
        db.commit()
    return {"unmatched": True}


# ---------- 채팅 (MVP: 텍스트/이모지, 폴링 방식) ----------

@router.get("/matches/{match_id}/messages")
def list_messages(
    match_id: uuid.UUID,
    before: uuid.UUID | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """최신 메시지부터 limit개. 더 이전 것은 before=<가장 오래된 message_id>로 요청."""
    match = _my_match(db, current, match_id)
    query = db.query(Message).filter(Message.match_id == match.id)
    if before:
        anchor = db.get(Message, before)
        if anchor and anchor.match_id == match.id:
            query = query.filter(Message.created_at < anchor.created_at)
    rows = query.order_by(Message.created_at.desc()).limit(limit).all()
    rows.reverse()
    # 상대의 내부 user_id 대신 is_mine만 보낸다
    return {
        "messages": [
            {"message_id": str(m.id), "body": m.body, "is_mine": m.sender_user_id == current.id, "sent_at": m.created_at.isoformat()}
            for m in rows
        ]
    }


@router.post("/matches/{match_id}/messages", status_code=status.HTTP_201_CREATED)
def send_message(
    match_id: uuid.UUID,
    payload: SendMessageRequest,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enforce_rate_limit(f"message:{current.id}", 30, 60)
    match = _my_match(db, current, match_id)
    message = Message(match_id=match.id, sender_user_id=current.id, body=payload.body)
    db.add(message)
    partner = match.partner_of(current.id)
    if not has_unread(db, partner, "NEW_MESSAGE", match.id):
        notify(db, partner, "NEW_MESSAGE", "새 메시지가 도착했어요", "매칭된 상대가 메시지를 보냈습니다.", match.id)
    db.commit()
    return {"message_id": str(message.id), "body": message.body, "is_mine": True, "sent_at": message.created_at.isoformat()}
