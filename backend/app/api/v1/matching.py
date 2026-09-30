"""/api/v1 — 추천(discover), LIKE/PASS, 매칭, 채팅."""

import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.rate_limit import enforce_rate_limit
from app.core.time import utcnow
from app.db.session import get_db
from app.deps import CurrentUser, get_current_user
from app.models.matching import Like, Match, MatchingPreference, Message, Report
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
    viewer = profile_service.people_from_profiles(db, [profile])[0]
    # 추천은 "나와 외모 등급이 비슷한 사람" 순서라서, 내 등급이 정해져야 추천을 볼 수 있다.
    # (사진은 승인됐지만 등급이 없는 예전 평가 → 관리자가 다시 정할 때까지 "평가 중"으로 안내)
    # 등급은 people_from_profiles가 이미 읽어 왔으므로 DB를 다시 조회하지 않는다.
    if viewer.tier is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="EVALUATION_REQUIRED")
    return viewer


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

    settings = get_settings()
    by_user = {p.user_id: p for p in profiles}
    ranked = matching_service.rank(
        viewer,
        profile_service.people_from_profiles(db, profiles),
        profile_service.matching_weights(),
        limit or settings.discover_page_size,
        liked_me=profile_service.liked_me_ids(db, current.id),
        liked_me_slots=settings.liked_me_slots,
        liked_me_probability=settings.liked_me_probability,
    )
    # 카드에는 외모 등급도, "나를 LIKE했는지"도 들어가지 않는다 (build_cards가 보내는 항목만 나감)
    cards = profile_service.build_cards(db, [by_user[p.user_id] for p in ranked])
    # 후보가 없을 때 조건을 자동으로 넓히지 않는다 (설계도 §56, §57)
    return {
        "profiles": cards,
        "empty": not cards,
        "likes_left_today": profile_service.likes_left_today(db, current.id),
        "daily_like_limit": settings.daily_like_limit,
    }


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
    target = _target(db, current, payload.profile_id)
    viewer = _viewer(db, current)

    # ID를 직접 넣어도, 추천 조건에 맞지 않는 사람에게는 LIKE할 수 없다 (설계도 금지사항 #18)
    if target.user_id in profile_service.excluded_user_ids(db, current.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="프로필을 찾을 수 없습니다.")
    candidates = profile_service.people_from_profiles(db, [target])
    if not candidates or not matching_service.mutually_compatible(viewer, candidates[0]):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="프로필을 찾을 수 없습니다.")

    # 하루 LIKE 한도 (한국 시간 자정에 다시 채워짐). DB로 세므로 서버를 재시작해도 초기화되지 않는다.
    limit = get_settings().daily_like_limit
    if profile_service.likes_sent_today(db, current.id) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"오늘 LIKE {limit}개를 모두 사용했어요. 자정(한국 시간)에 다시 충전돼요.",
        )

    _upsert_action(db, current.id, target.user_id, "LIKE")
    db.flush()
    # 한 번 더 확인: LIKE를 여러 개 "동시에" 보내면 위의 확인을 모두 통과할 수 있다.
    # 방금 기록한 LIKE를 포함해 세고, 한도를 넘으면 취소한다.
    # (SQLite는 쓰기를 한 번에 하나씩만 하므로, 여기서 세는 숫자에는 먼저 끝난 요청이 모두 들어 있다)
    if profile_service.likes_sent_today(db, current.id) > limit:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"오늘 LIKE {limit}개를 모두 사용했어요. 자정(한국 시간)에 다시 충전돼요.",
        )

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
    return {
        "matched": match is not None,
        "match_id": str(match.id) if match else None,
        "likes_left_today": profile_service.likes_left_today(db, current.id),
    }


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


def _last_messages(db: Session, match_ids: list[uuid.UUID]) -> dict[uuid.UUID, Message]:
    """대화방마다 가장 최근 메시지 1개 (쿼리 1번)."""
    if not match_ids:
        return {}
    ranked = (
        select(
            Message.id,
            func.row_number()
            .over(partition_by=Message.match_id, order_by=(Message.created_at.desc(), Message.id.desc()))
            .label("rn"),
        )
        .where(Message.match_id.in_(match_ids))
        .subquery()
    )
    rows = db.query(Message).join(ranked, ranked.c.id == Message.id).filter(ranked.c.rn == 1).all()
    return {m.match_id: m for m in rows}


@router.get("/matches")
def list_matches(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    matches = (
        db.query(Match)
        .filter(((Match.user_a_id == current.id) | (Match.user_b_id == current.id)) & (Match.status == "ACTIVE"))
        .order_by(Match.created_at.desc())
        .all()
    )
    cards = _partner_cards(db, matches, current.id)
    # 차단 관계와 마지막 메시지를 매칭마다 따로 묻지 않고 한 번에 가져온다 (매칭이 20개여도 쿼리 2번)
    blocked = profile_service.blocked_user_ids(db, current.id)
    last_messages = _last_messages(db, [m.id for m in matches])
    result = []
    for m in matches:
        partner = m.partner_of(current.id)
        if partner not in cards or partner in blocked:
            continue
        last = last_messages.get(m.id)
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


@router.get("/matches/ended")
def list_ended_matches(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """끝난 대화 목록 (매칭 해제·차단·상대 탈퇴 등). 대화 내용은 볼 수 없고, 신고만 할 수 있다.

    끝난 이유(누가 해제·차단했는지)는 알려주지 않는다.
    """
    since = utcnow() - timedelta(days=90)
    matches = (
        db.query(Match)
        .filter(
            ((Match.user_a_id == current.id) | (Match.user_b_id == current.id)),
            Match.status != "ACTIVE",
            Match.ended_at >= since,
        )
        .order_by(Match.ended_at.desc())
        .limit(50)
        .all()
    )
    partner_ids = [m.partner_of(current.id) for m in matches]
    nicknames = dict(
        db.query(PublicProfile.user_id, PublicProfile.nickname).filter(PublicProfile.user_id.in_(partner_ids)).all()
    ) if partner_ids else {}
    reported = {
        uid
        for (uid,) in db.query(Report.reported_user_id).filter(
            Report.reporter_user_id == current.id,
            Report.reported_user_id.in_(partner_ids),
            Report.status.in_(["OPEN", "IN_REVIEW"]),
        )
    } if partner_ids else set()
    return {
        "matches": [
            {
                "match_id": str(m.id),
                "partner_nickname": nicknames.get(m.partner_of(current.id)) or "탈퇴한 사용자",
                "matched_at": m.created_at.isoformat(),
                "ended_at": m.ended_at.isoformat() if m.ended_at else None,
                "report_pending": m.partner_of(current.id) in reported,
            }
            for m in matches
        ]
    }


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
    after: uuid.UUID | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """최신 메시지부터 limit개.

    - 더 이전 것: before=<가장 오래된 message_id>
    - 새로 온 것만: after=<화면에 있는 마지막 message_id> → 채팅 화면이 몇 초마다 부르는 방식.
      새 메시지가 없으면 빈 목록이라 서버·데이터 사용량이 훨씬 적다.
      (같은 시각에 저장된 메시지를 놓치지 않도록 "같은 시각 이상"으로 가져오고, 화면에서 중복을 걸러낸다)
    """
    match = _my_match(db, current, match_id)
    query = db.query(Message).filter(Message.match_id == match.id)
    anchor_id = after or before
    anchor = db.get(Message, anchor_id) if anchor_id else None
    if anchor is not None and anchor.match_id != match.id:
        anchor = None
    if after and anchor is not None:
        rows = (
            query.filter(Message.created_at >= anchor.created_at, Message.id != anchor.id)
            .order_by(Message.created_at.asc(), Message.id.asc())
            .limit(limit)
            .all()
        )
    else:
        if before and anchor is not None:
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
