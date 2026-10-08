"""/api/v1 — 추천(discover), LIKE/PASS, 매칭, 채팅."""

import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.rate_limit import enforce_rate_limit
from app.core.time import as_utc, utcnow
from app.db.session import get_db
from app.deps import CurrentUser, get_current_user
from app.models.matching import Like, Match, MatchingPreference, MatchRead, Message, Report
from app.models.profile import PublicProfile
from app.models.user import User
from app.schemas.matching import SendMessageRequest, TargetRequest
from app.services import (
    match_limit_service,
    matching_service,
    membership_service,
    profile_service,
    push_service,
    vip_service,
)
from app.services.notification_service import has_unread, notify, notify_match_created

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
    # 첫 이용권 입금 전 (2026-10-03, 2026-10-04 구독제). 사진보다 먼저 안내한다 (가입 단계).
    if membership_service.needs_first_payment(
        current.user, has_approved_photo=profile_service.has_approved_photo(db, current.id)
    ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="PAYMENT_REQUIRED")
    if get_settings().require_approved_photo_to_discover and not profile_service.has_approved_photo(db, current.id):
        # 사진을 "냈는데 기다리는 중"과 "아직 안 냄(또는 반려)"을 나눠서 알려준다.
        # (2026-10-01: 사진을 안 낸 사람에게도 "검수 대기 중"이라고 보여줘서 제출을 빼먹는 문제가 있었다)
        if profile_service.has_pending_photo(db, current.id):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="PHOTO_APPROVAL_REQUIRED")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="PHOTO_REQUIRED")
    viewer = profile_service.people_from_profiles(db, [profile])[0]
    # 추천은 "나와 외모 등급이 비슷한 사람" 순서라서, 내 등급이 정해져야 추천을 볼 수 있다.
    # (사진은 승인됐지만 등급이 없는 예전 평가 → 관리자가 다시 정할 때까지 "평가 중"으로 안내)
    # 등급은 people_from_profiles가 이미 읽어 왔으므로 DB를 다시 조회하지 않는다.
    if viewer.tier is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="EVALUATION_REQUIRED")
    _require_membership(db, current)
    return viewer


def _require_membership(db: Session, current: CurrentUser) -> None:
    """추천·PASS 전에 부르는 공통 처리.

    2026-10-06 무료 체험: 이용권이 없어도(체험 중·체험 끝·이용권 끝) 추천 보기·PASS는 된다. LIKE만 막는다 (like()).
    점검 기간은 없앴다 (유료 시작 시각 전에는 베타처럼 모두 무료).
    """
    user = current.user
    # 쌓아 둔 일수가 있는데 이미 추천이 열린 상태면 지금 시작한다 (등급을 정할 때 시작하지만, 혹시 빠졌을 때를 대비)
    if membership_service.enabled() and (user.member_days_banked or 0) > 0 and membership_service.start_banked(db, user):
        db.commit()


def _never_paid(user: User) -> bool:
    return user.member_until is None and user.vip_until is None and not (user.member_days_banked or 0)


def _like_blocked_detail(user: User) -> str:
    """LIKE를 못 할 때 이유. 상대가 나를 LIKE했든 안 했든 똑같이 응답한다 (누가 나를 좋아하는지 드러나지 않게)."""
    return "TRIAL_ENDED" if _never_paid(user) else "MEMBERSHIP_REQUIRED"


# ---------- 추천 ----------

@router.get("/discover")
def discover(
    limit: int | None = Query(default=None, ge=1, le=20),
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enforce_rate_limit(f"discover:{current.id}", 60, 60)
    viewer = _viewer(db, current)
    # VIP는 PASS한 사람이 24시간 뒤 다시 나온다 (무료 48시간, 2026-10-03)
    cooldown = vip_service.pass_cooldown_hours(current.user)
    excluded = profile_service.excluded_user_ids(db, current.id, pass_cooldown_hours=cooldown)

    # 하루 매칭 한도 (2026-10-06): 오늘 매칭이 3번 생겼으면, 오늘은 "나를 이미 LIKE한 사람"을 추천에서 뺀다.
    # 본인은 모르게 한다 (응답에 아무 표시도 없음). 한국 시간 밤 12시에 자동으로 풀린다.
    # VIP "받은 LIKE" 목록은 그대로다.
    limit_reached = match_limit_service.reached_daily_limit(db, current.user)
    if limit_reached:
        excluded = set(excluded) | match_limit_service.all_liker_ids(db, current.id)

    query = profile_service.discoverable_profiles_query(db, current.user.university_id).filter(
        PublicProfile.user_id.notin_(excluded)
    )
    # 성별은 DB에서 먼저 거르고(빠름), 나머지 조건은 매칭 엔진에서 양방향으로 확인
    if viewer.preferences and viewer.preferences.preferred_gender != "ANY":
        query = query.filter(PublicProfile.gender == viewer.preferences.preferred_gender)
    profiles = query.all()

    settings = get_settings()
    like_limit = vip_service.daily_like_limit(current.user)
    access = membership_service.like_access(current.user)
    by_user = {p.user_id: p for p in profiles}
    # LIKE를 못 하는 사람(체험 다 씀·이용권 끝)은 같은 등급 안에서 뒤로. 단, 이미 나를 LIKE한 사람은 그대로 둔다
    # (내가 LIKE하면 상대가 아무것도 안 해도 바로 매칭이 되니까)
    likers = {uid for uid, _ in profile_service.likers_of(db, current.id)}
    cannot_like = membership_service.cannot_like_ids(db, list(by_user)) - likers
    ranked = matching_service.rank(
        viewer,
        profile_service.people_from_profiles(db, profiles),
        profile_service.matching_weights(),
        limit or settings.discover_page_size,
        liked_me=set() if limit_reached else profile_service.liked_me_ids(db, current.id),
        liked_me_slots=settings.liked_me_slots,
        liked_me_probability=settings.liked_me_probability,
        seen_before=profile_service.passed_before_ids(db, current.id, pass_cooldown_hours=cooldown),
        cannot_like=cannot_like,
    )
    # 카드에는 외모 등급도, "나를 LIKE했는지"도 들어가지 않는다 (build_cards가 보내는 항목만 나감)
    cards = profile_service.build_cards(db, [by_user[p.user_id] for p in ranked])
    # 후보가 없을 때 조건을 자동으로 넓히지 않는다 (설계도 §56, §57)
    trial = access != "paid"
    return {
        "profiles": cards,
        "empty": not cards,
        # 무료 체험 (2026-10-06): paid / trial / none. 체험이면 남은 LIKE는 "평생 남은 체험 LIKE"
        "like_access": access,
        "trial_likes_left": membership_service.trial_left(current.user),
        "trial_like_limit": membership_service.trial_limit(),
        "likes_left_today": membership_service.trial_left(current.user)
        if trial
        else profile_service.likes_left_today(db, current.id, like_limit),
        "daily_like_limit": membership_service.trial_limit() if trial else like_limit,
        # VIP는 하트를 "5+5"로 보여준다 (무료 몫 5개 + VIP 몫 5개)
        "vip": vip_service.is_vip(current.user),
        "base_like_limit": settings.daily_like_limit,
    }


# ---------- 받은 LIKE (VIP 혜택 3, 2026-10-03) ----------

@router.get("/liked-me")
def liked_me(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """나를 LIKE한 사람 목록 (VIP 전용). 최근 LIKE 순.

    - 추천 필수 조건(차단, 성별·나이·캠퍼스·같은 과 제외)을 추천과 똑같이 양방향으로 적용한다.
    - 이미 매칭된 사람, 내가 LIKE한 사람은 없다. 내가 PASS한 사람은 "passed"로 표시해서 보여준다.
    - 무료 사용자에게는 아무것도 알려주지 않는다 (숫자도 없음) → 403 VIP_REQUIRED.
    - 사진은 원래처럼 보내지 않는다 (카드는 추천과 같은 build_cards).
    """
    enforce_rate_limit(f"liked-me:{current.id}", 60, 60)
    viewer = _viewer(db, current)
    if not vip_service.is_vip(current.user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="VIP_REQUIRED")

    # 매칭 정지된 사람(2026-10-05): 받은 LIKE에 답해도 매칭이 안 뜨므로, 이상하게 느끼지 않게 목록을 비워 둔다
    if current.user.match_suspended:
        return {"profiles": []}
    likers = profile_service.likers_of(db, current.id)
    excluded = profile_service.excluded_user_ids(db, current.id, include_passed=False)
    liked_at = {uid: at for uid, at in likers if uid not in excluded}
    if not liked_at:
        return {"profiles": []}
    # 이용권이 끝난 사람도 보여준다 (이미 나를 LIKE했으니, LIKE하면 바로 매칭 → 대화는 이용권 없이도 된다)
    profiles = (
        profile_service.discoverable_profiles_query(db, current.user.university_id, members_only=False)
        .filter(PublicProfile.user_id.in_(list(liked_at)))
        .all()
    )
    people = {p.user_id: p for p in profile_service.people_from_profiles(db, profiles)}
    ok = [p for p in profiles if p.user_id in people and matching_service.mutually_compatible(viewer, people[p.user_id])]
    ok.sort(key=lambda p: liked_at[p.user_id], reverse=True)
    passed = {to_id for to_id, _ in profile_service._passes(db, current.id)}
    cards = profile_service.build_cards(db, ok)
    return {
        "profiles": [
            {**card, "liked_at": liked_at[p.user_id].isoformat(), "passed": p.user_id in passed}
            for p, card in zip(ok, cards)
        ]
    }


# ---------- LIKE / PASS ----------

def _target(db: Session, current: CurrentUser, profile_id: uuid.UUID) -> PublicProfile:
    target = profile_service.find_active_profile(db, profile_id)
    if target is None or target.user_id == current.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="프로필을 찾을 수 없습니다.")
    return target


def _upsert_action(db: Session, from_id: uuid.UUID, to_id: uuid.UUID, action: str, *, is_trial: bool = False) -> None:
    row = db.query(Like).filter(Like.from_user_id == from_id, Like.to_user_id == to_id).first()
    if row is None:
        db.add(Like(from_user_id=from_id, to_user_id=to_id, action=action, is_trial=is_trial))
    elif action == "LIKE":
        # PASS 48시간이 지나 다시 나온 사람에게 LIKE하는 경우: PASS 행을 지우고 새로 만든다.
        # 하루 LIKE 개수는 created_at으로 세기 때문 (행을 고쳐 쓰면 예전 PASS 날짜가 남아서 개수에 안 잡힌다 → 하루 5개 제한을 피할 수 있음)
        db.delete(row)
        db.flush()
        db.add(Like(from_user_id=from_id, to_user_id=to_id, action=action, is_trial=is_trial))
    else:
        # 다시 PASS: 값이 같으면 SQLAlchemy가 updated_at을 안 바꾸므로 직접 바꾼다 (48시간을 이때부터 다시 셈)
        row.action = action
        row.updated_at = utcnow()


@router.post("/likes")
def like(payload: TargetRequest, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    enforce_rate_limit(f"like:{current.id}", 60, 60)
    target = _target(db, current, payload.profile_id)
    viewer = _viewer(db, current)
    vip = vip_service.is_vip(current.user)
    # 무료 체험 (2026-10-06): 이용권이 없으면 체험 LIKE(평생 3개)로만. 다 쓰면 상대가 누구든 똑같이 막는다.
    access = membership_service.like_access(current.user)
    if access == "none":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_like_blocked_detail(current.user))

    # ID를 직접 넣어도, 추천 조건에 맞지 않는 사람에게는 LIKE할 수 없다 (설계도 금지사항 #18)
    excluded = profile_service.excluded_user_ids(
        db, current.id, pass_cooldown_hours=vip_service.pass_cooldown_hours(current.user)
    )
    if target.user_id in excluded:
        # VIP "받은 LIKE" 목록에서는 내가 PASS했던 사람에게도 LIKE할 수 있다 (2026-10-03).
        # 그 사람이 나를 LIKE했고, PASS 말고 다른 이유(차단·매칭·이미 LIKE)로 빠진 게 아니어야 한다.
        allowed = (
            vip
            and target.user_id in {uid for uid, _ in profile_service.likers_of(db, current.id)}
            and target.user_id not in profile_service.excluded_user_ids(db, current.id, include_passed=False)
        )
        if not allowed:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="프로필을 찾을 수 없습니다.")
    candidates = profile_service.people_from_profiles(db, [target])
    if not candidates or not matching_service.mutually_compatible(viewer, candidates[0]):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="프로필을 찾을 수 없습니다.")

    if access == "trial":
        # 체험 LIKE: 하루 한도가 아니라 평생 개수. 동시에 눌러도 넘지 않게 DB에서 조건부로 1 늘린다.
        if not membership_service.use_trial_like(db, current.user):
            db.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_like_blocked_detail(current.user))
        _upsert_action(db, current.id, target.user_id, "LIKE", is_trial=True)
        db.flush()
    else:
        # 하루 LIKE 한도 (한국 시간 자정에 다시 채워짐). DB로 세므로 서버를 재시작해도 초기화되지 않는다.
        # 무료 5개, VIP 10개 (2026-10-03). "받은 LIKE" 목록에서 누른 LIKE도 여기에 포함된다.
        limit = vip_service.daily_like_limit(current.user)
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
        # 매칭 정지 (2026-10-05): 둘 중 한 명이라도 정지면 숨김 매칭으로 만든다.
        # 두 사람 모두에게 매칭·알림이 보이지 않고, 관리자가 "다시 보이게"를 누르면 그때 알림이 간다.
        hidden = current.user.match_suspended or bool(
            db.query(User.match_suspended).filter(User.id == target.user_id).scalar()
        )
        match = Match(user_a_id=a, user_b_id=b, status="HIDDEN" if hidden else "ACTIVE")
        db.add(match)
        db.flush()
        if not hidden:
            for uid in (a, b):
                # 방금 LIKE를 누른 본인은 화면에서 바로 보므로 휴대폰 알림은 상대에게만
                notify_match_created(db, uid, match.id, push=uid != current.id)
    try:
        db.commit()
    except IntegrityError:
        # 두 사람이 거의 동시에 LIKE한 경우: 이미 만들어진 매칭을 사용
        db.rollback()
        a, b = profile_service.match_pair(current.id, target.user_id)
        match = db.query(Match).filter(Match.user_a_id == a, Match.user_b_id == b).first()

    # 매칭되기 전에는 상대가 나를 LIKE했는지 알려주지 않는다 (설계도 §23)
    # 숨김 매칭은 "매칭 안 됨"과 똑같이 응답한다 (매칭 정지 사실을 알 수 없게)
    visible = match is not None and match.status == "ACTIVE"
    trial = access == "trial"
    return {
        "matched": visible,
        "match_id": str(match.id) if visible else None,
        "like_access": membership_service.like_access(current.user),
        "trial_likes_left": membership_service.trial_left(current.user),
        "likes_left_today": membership_service.trial_left(current.user)
        if trial
        else profile_service.likes_left_today(db, current.id, vip_service.daily_like_limit(current.user)),
    }


@router.post("/passes")
def pass_profile(payload: TargetRequest, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    enforce_rate_limit(f"pass:{current.id}", 120, 60)
    _require_membership(db, current)
    target = _target(db, current, payload.profile_id)
    _upsert_action(db, current.id, target.user_id, "PASS")
    db.commit()
    return {"passed": True}


@router.delete("/passes/{profile_id}")
def undo_pass(profile_id: uuid.UUID, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """PASS 취소 (향후 Undo 기능용, 설계도 §21)."""
    _require_membership(db, current)
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
    # 숨김 매칭(매칭 정지)은 없는 것처럼 404
    if match is None or not match.has_member(current.id) or match.status == "HIDDEN":
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


def _unread_counts(db: Session, match_ids: list[uuid.UUID], user_id: uuid.UUID) -> dict[uuid.UUID, int]:
    """대화방마다 안 읽은 상대 메시지 수 (2026-10-08, 쿼리 1번).
    마지막으로 읽은 시각(match_reads)보다 늦게 온 상대 메시지를 센다. 읽은 기록이 없으면 상대 메시지 전부."""
    if not match_ids:
        return {}
    rows = (
        db.query(Message.match_id, func.count(Message.id))
        .outerjoin(MatchRead, (MatchRead.match_id == Message.match_id) & (MatchRead.user_id == user_id))
        .filter(
            Message.match_id.in_(match_ids),
            Message.sender_user_id != user_id,
            (MatchRead.last_read_at.is_(None)) | (Message.created_at > MatchRead.last_read_at),
        )
        .group_by(Message.match_id)
        .all()
    )
    return {mid: n for mid, n in rows}


def _mark_read(db: Session, match_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """대화방을 열어 메시지를 받아 갔으면 "여기까지 읽음"으로 기록한다 (2026-10-08).
    상대의 가장 최근 메시지 시각으로 적는다. 바뀐 게 없으면 DB에 쓰지 않는다 (4초마다 불려도 가볍게)."""
    latest = (
        db.query(func.max(Message.created_at))
        .filter(Message.match_id == match_id, Message.sender_user_id != user_id)
        .scalar()
    )
    if latest is None:
        return
    row = db.get(MatchRead, (match_id, user_id))
    if row is None:
        db.add(MatchRead(match_id=match_id, user_id=user_id, last_read_at=latest))
    elif row.last_read_at is None or as_utc(row.last_read_at) < as_utc(latest):
        row.last_read_at = latest
    else:
        return
    try:
        db.commit()
    except IntegrityError:  # 같은 사람이 두 화면에서 동시에 열었을 때
        db.rollback()


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
    unread = _unread_counts(db, [m.id for m in matches], current.id)

    # 대화 목록은 "마지막으로 대화가 오간 시간" 기준 최신순으로 보여준다.
    # 메시지가 없는 매칭은 매칭된 시간을 기준으로 삼는다.
    def _last_activity(m: Match):
        last = last_messages.get(m.id)
        return last.created_at if last else m.created_at

    matches.sort(key=_last_activity, reverse=True)

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
                "unread_count": unread.get(m.id, 0),  # 안 읽은 상대 메시지 수 (2026-10-08)
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
            # 숨김 매칭(HIDDEN)은 끝난 대화에도 절대 나오지 않는다
            Match.status.in_(["UNMATCHED", "BLOCKED"]),
            Match.ended_at >= since,
        )
        .order_by(Match.ended_at.desc())
        .limit(50)
        .all()
    )
    partner_ids = [m.partner_of(current.id) for m in matches]
    # 탈퇴한 사람은 7일 동안 프로필이 남아 있지만(관리자 확인용), 다른 사용자에게는 "탈퇴한 사용자"로 보여준다
    nicknames = dict(
        db.query(PublicProfile.user_id, PublicProfile.nickname)
        .join(User, User.id == PublicProfile.user_id)
        .filter(PublicProfile.user_id.in_(partner_ids), User.deleted_at.is_(None))
        .all()
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
    # 지금 이 대화방 화면을 보고 있다는 표시 (메모리에만) → 이 방의 새 메시지는 휴대폰 알림을 생략한다
    push_service.mark_viewing(current.id, match.id)
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
    # 읽음 기록 (2026-10-08): 처음 열 때, 또는 새로 받아 간 메시지에 상대 메시지가 있을 때만 (예전 메시지 더 보기는 제외)
    if not before and (after is None or any(m.sender_user_id != current.id for m in rows)):
        _mark_read(db, match.id, current.id)
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
    # 휴대폰 알림 (못 켠 사람은 메일): 메시지마다. 상대가 지금 이 대화방을 보고 있으면 안 보냄 (2026-10-06)
    push_service.queue(db, partner, push_service.MESSAGE, match.id)
    db.commit()
    return {"message_id": str(message.id), "body": message.body, "is_mine": True, "sent_at": message.created_at.isoformat()}
