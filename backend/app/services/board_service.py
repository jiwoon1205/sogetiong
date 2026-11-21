"""자유게시판 · 쪽지 (2026-11-22, 프로젝트 문서 `자유게시판·쪽지 설계 (2026-11-22)`).

게시판 프로필
- 가입 과정은 그대로다. 가입할 때는 게시판 프로필이 없고 게시판도 볼 수 없다.
- 게시판 탭에서 "프로필 만들기"로 만든다. **사진 검수가 끝난 사람만** 만들 수 있다.
- 소개팅 프로필과 완전히 따로다. 다른 사람에게 보이는 것: 닉네임 · 프사 · 성별 · 학교(캠퍼스) · (고르면) 점수 1개.
  게시판·쪽지 어디에서도 소개팅 프로필(닉네임·사진·자기소개·나이 등)은 보이지 않는다.
- 닉네임은 30일에 한 번 바꿀 수 있다. 프사는 직접 올리면 검수 없이 바로 보인다 (신고 3번이면 기본 그림으로).

게시판 3개 (2026-11-22 추가)
- 자유 게시판: 모두. 연애 게시판: 찾는 관계가 "진지한 연애"인 사람만. 캐주얼 게시판: "캐주얼한 만남"인 사람만.
  들어갈 수 없는 게시판은 목록에도 안 보이고 글·댓글을 읽을 수도 없다. 찾는 관계를 바꾸면 바로 따라 바뀐다.
- 성적인 이야기는 캐주얼 게시판에서만 된다. 자유·연애 게시판에서 하면 게시판 이용 정지 (신고 사유 "성적인 이야기").

글 · 댓글
- 글만(사진 첨부 없음). 하루 글 5개, 댓글 50개.
- 차단한(차단당한) 사람의 글·댓글은 서로 안 보인다. 같은 과 제외 등 매칭 조건은 쓰지 않는다.
- 신고 3번(서로 다른 사람) → 자동 숨김. 관리자는 신고 없이도 즉시 지울 수 있다.
- 탈퇴한 사람의 글·댓글은 "탈퇴한 사용자"로 남는다.

쪽지
- 게시판에서 상대 프로필(글·댓글 작성자)에게 쪽지를 열 때 슈퍼 라이크 1개. 여성은 하루 3개까지 무료.
- 매칭 대화방과 따로인 쪽지방. 두 사람 사이에 하나만. 받은 사람이 답장하기 전에는 연 사람이 1개만 보낼 수 있다.
- 답장은 무료. 누구든 나가면 방이 닫히고 더는 못 보낸다. 차단하면 닫힌다.

게시판 이용 정지 (관리자)
- 정지 기간에는 글·댓글·쪽지 보내기가 막힌다 (읽기와 받은 쪽지 보기는 된다). 소개팅은 그대로.
- 정지·해제하면 사용자에게 알림(앱 알림 + 휴대폰 알림, 휴대폰 알림이 안 되면 메일).
"""

import uuid
from datetime import datetime, timedelta

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.time import KST, as_utc, kst_day_start, utcnow
from app.models.board import (
    BOARD_REPORT_REASONS,
    BOARD_REQUIRED_GOAL,
    BOARDS,
    BOARD_REPORT_TARGETS,
    SCORE_KEYS,
    BoardComment,
    BoardPost,
    BoardProfile,
    BoardReport,
    NoteMessage,
    NoteRoom,
)
from app.models.matching import Block
from app.models.profile import PublicProfile
from app.models.university import Campus, University
from app.models.user import User
from app.services import notification_service, profile_service, push_service, super_like_service, vip_service
from app.services.storage_service import get_storage

NICKNAME_MIN, NICKNAME_MAX = 2, 12
NICKNAME_CHANGE_DAYS = 30
TITLE_MAX, BODY_MAX, COMMENT_MAX, NOTE_MAX = 40, 2000, 500, 1000
DAILY_POSTS, DAILY_COMMENTS = 5, 50
FEMALE_FREE_NOTES_PER_DAY = 3
AUTO_HIDE_REPORTS = 3
PAGE_SIZE = 20
PERMANENT_BAN = datetime(2999, 12, 31, tzinfo=KST)
DELETED_NAME = "탈퇴한 사용자"
AVATAR_MAX_SIDE = 512

SCORE_LABELS = {
    "overall_impression": "인상",
    "style": "스타일",
    "grooming": "자기관리",
    "photo_vibe": "사진 분위기",
}


class BoardError(Exception):
    def __init__(self, message: str, code: str = "INVALID", status: int = 409):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status


# ---------- 게시판 프로필 ----------

def get_profile(db: Session, user_id: uuid.UUID) -> BoardProfile | None:
    return db.query(BoardProfile).filter(BoardProfile.user_id == user_id).first()


def require_profile(db: Session, user: User) -> BoardProfile:
    """게시판 프로필이 있어야 게시판을 볼 수 있다."""
    profile = get_profile(db, user.id)
    if profile is None:
        raise BoardError("게시판 프로필을 먼저 만들어 주세요.", "NO_BOARD_PROFILE", 403)
    return profile


def is_banned(profile: BoardProfile, now: datetime | None = None) -> bool:
    return profile.banned_until is not None and as_utc(profile.banned_until) > (now or utcnow())


def require_not_banned(profile: BoardProfile) -> None:
    if is_banned(profile):
        raise BoardError("게시판 이용이 정지된 상태예요.", "BOARD_BANNED", 403)


def can_create(db: Session, user: User) -> tuple[bool, str | None]:
    """게시판 프로필을 만들 수 있나. (False, 이유)"""
    if user.status != "ACTIVE":
        return False, "INACTIVE"
    if not profile_service.has_approved_photo(db, user.id):
        return False, "PHOTO_NOT_APPROVED"
    return True, None


def normalize_nickname(raw: str) -> str:
    name = " ".join((raw or "").split())
    if not (NICKNAME_MIN <= len(name) <= NICKNAME_MAX):
        raise BoardError(f"닉네임은 {NICKNAME_MIN}~{NICKNAME_MAX}자로 정해 주세요.", "NICKNAME_LENGTH", 422)
    if name == DELETED_NAME or "운영" in name or "관리자" in name or "훕팅" in name:
        raise BoardError("쓸 수 없는 닉네임이에요.", "NICKNAME_RESERVED", 422)
    return name


def _nickname_taken(db: Session, name: str, except_id: uuid.UUID | None = None) -> bool:
    q = db.query(BoardProfile.id).filter(func.lower(BoardProfile.nickname) == name.lower())
    if except_id is not None:
        q = q.filter(BoardProfile.id != except_id)
    return q.first() is not None


def _check_score(score: str | None) -> str | None:
    if score in (None, "", "NONE"):
        return None
    if score not in SCORE_KEYS:
        raise BoardError("공개할 점수를 다시 골라 주세요.", "SCORE_KEY", 422)
    return score


def create_profile(db: Session, user: User, nickname: str, shown_score: str | None) -> BoardProfile:
    if get_profile(db, user.id) is not None:
        raise BoardError("이미 게시판 프로필이 있어요.", "ALREADY", 409)
    ok, reason = can_create(db, user)
    if not ok:
        raise BoardError("사진 검수가 끝나면 게시판을 이용할 수 있어요.", reason or "NOT_ALLOWED", 403)
    name = normalize_nickname(nickname)
    if _nickname_taken(db, name):
        raise BoardError("이미 쓰고 있는 닉네임이에요.", "NICKNAME_TAKEN", 409)
    profile = BoardProfile(user_id=user.id, nickname=name, shown_score=_check_score(shown_score))
    db.add(profile)
    db.flush()
    return profile


def next_nickname_change(profile: BoardProfile) -> datetime:
    return as_utc(profile.nickname_changed_at) + timedelta(days=NICKNAME_CHANGE_DAYS)


def update_profile(db: Session, profile: BoardProfile, *, nickname: str | None, shown_score: str | None, score_given: bool) -> None:
    if nickname is not None:
        name = normalize_nickname(nickname)
        if name != profile.nickname:
            if utcnow() < next_nickname_change(profile):
                raise BoardError("닉네임은 30일에 한 번 바꿀 수 있어요.", "NICKNAME_COOLDOWN", 409)
            if _nickname_taken(db, name, profile.id):
                raise BoardError("이미 쓰고 있는 닉네임이에요.", "NICKNAME_TAKEN", 409)
            profile.nickname = name
            profile.nickname_changed_at = utcnow()
    if score_given:
        profile.shown_score = _check_score(shown_score)


def set_avatar(db: Session, profile: BoardProfile, processed) -> None:
    storage = get_storage()
    key = f"board/{profile.user_id}/{uuid.uuid4()}.jpg"
    storage.save(key, processed.data)
    old = profile.avatar_key
    profile.avatar_key = key
    if old:
        _delete_file(old)


def clear_avatar(profile: BoardProfile) -> None:
    old = profile.avatar_key
    profile.avatar_key = None
    if old:
        _delete_file(old)


def _delete_file(key: str) -> None:
    try:
        get_storage().delete(key)
    except FileNotFoundError:
        pass


def read_avatar(profile: BoardProfile) -> bytes | None:
    if not profile.avatar_key:
        return None
    try:
        return get_storage().read(profile.avatar_key)
    except FileNotFoundError:
        return None


def my_scores(db: Session, user_id: uuid.UUID) -> dict[str, int] | None:
    evaluation = profile_service.latest_evaluations(db, [user_id]).get(user_id)
    return evaluation.scores() if evaluation else None


# ---------- 다른 사람에게 보이는 게시판 프로필 ----------

def public_views(db: Session, user_ids: set[uuid.UUID]) -> dict[uuid.UUID, dict]:
    """작성자 표시용. 소개팅 프로필에서 성별·학교(캠퍼스)만 가져온다 (닉네임·사진·나이 등은 절대 안 씀)."""
    ids = list(user_ids)
    if not ids:
        return {}
    profiles = {p.user_id: p for p in db.query(BoardProfile).filter(BoardProfile.user_id.in_(ids))}
    users = {u.id: u for u in db.query(User).filter(User.id.in_(ids))}
    dating = {p.user_id: p for p in db.query(PublicProfile).filter(PublicProfile.user_id.in_(ids))}
    campus_ids = {p.campus_id for p in dating.values() if p.campus_id}
    campuses = {c.id: c for c in db.query(Campus).filter(Campus.id.in_(campus_ids))} if campus_ids else {}
    uni_names = dict(db.query(University.id, University.name).all())
    need_scores = [uid for uid, p in profiles.items() if p.shown_score]
    evaluations = profile_service.latest_evaluations(db, need_scores) if need_scores else {}
    out: dict[uuid.UUID, dict] = {}
    for uid in ids:
        profile = profiles.get(uid)
        user = users.get(uid)
        if profile is None or user is None or user.deleted_at is not None or user.status == "DELETED":
            out[uid] = {"id": None, "nickname": DELETED_NAME, "has_avatar": False, "gender": None,
                        "school": None, "campus": None, "score": None, "deleted": True}
            continue
        dp = dating.get(uid)
        campus = campuses.get(dp.campus_id) if dp and dp.campus_id else None
        score = None
        evaluation = evaluations.get(uid)
        if profile.shown_score and evaluation is not None:
            score = {"key": profile.shown_score, "label": SCORE_LABELS[profile.shown_score],
                     "value": evaluation.scores()[profile.shown_score]}
        out[uid] = {
            "id": str(profile.id),
            "nickname": profile.nickname,
            "has_avatar": bool(profile.avatar_key),
            "avatar_version": profile.updated_at.isoformat() if profile.avatar_key else None,
            "gender": dp.gender if dp else None,
            "school": uni_names.get(user.university_id),
            "campus": campus.name if campus else None,
            "score": score,
            "deleted": False,
        }
    return out


def own_view(db: Session, user: User, profile: BoardProfile) -> dict:
    view = public_views(db, {user.id})[user.id]
    return {
        **view,
        "shown_score": profile.shown_score,
        "next_nickname_change": next_nickname_change(profile).isoformat(),
        "banned_until": as_utc(profile.banned_until).isoformat() if is_banned(profile) else None,
        "ban_permanent": is_banned(profile) and as_utc(profile.banned_until).year >= 2999,
        "ban_reason": profile.ban_reason if is_banned(profile) else None,
    }


# ---------- 게시판 3개 ----------

BOARD_NAMES = {"FREE": "자유 게시판", "LOVE": "연애 게시판", "CASUAL": "캐주얼 게시판"}
SEXUAL_RULE = "성적인 이야기는 캐주얼 게시판에서만 할 수 있어요. 어기면 게시판 이용이 정지돼요."


def relationship_goal(db: Session, user_id: uuid.UUID) -> str | None:
    row = db.query(PublicProfile.relationship_goal).filter(PublicProfile.user_id == user_id).first()
    return row[0] if row else None


def allowed_boards(db: Session, user_id: uuid.UUID) -> list[str]:
    goal = relationship_goal(db, user_id)
    return [b for b in BOARDS if BOARD_REQUIRED_GOAL.get(b) in (None, goal)]


def require_board(db: Session, user_id: uuid.UUID, board: str) -> None:
    if board not in BOARDS:
        raise BoardError("없는 게시판이에요.", "NOT_FOUND", 404)
    if board not in allowed_boards(db, user_id):
        need = "진지한 연애" if BOARD_REQUIRED_GOAL[board] == "SERIOUS" else "캐주얼한 만남"
        raise BoardError(f"찾는 관계가 '{need}'인 사람만 들어갈 수 있어요.", "BOARD_NOT_ALLOWED", 403)


def boards_view(db: Session, user_id: uuid.UUID) -> list[dict]:
    allowed = allowed_boards(db, user_id)
    return [
        {"key": b, "name": BOARD_NAMES[b], "allowed": b in allowed,
         "sexual_rule": None if b == "CASUAL" else SEXUAL_RULE}
        for b in BOARDS
    ]


# ---------- 차단 ----------

def blocked_ids(db: Session, user_id: uuid.UUID) -> set[uuid.UUID]:
    """내가 차단했거나 나를 차단한 사람."""
    rows = db.query(Block.blocker_user_id, Block.blocked_user_id).filter(
        or_(Block.blocker_user_id == user_id, Block.blocked_user_id == user_id)
    )
    return {b if a == user_id else a for a, b in rows}


def profile_owner(db: Session, board_profile_id: uuid.UUID, viewer_id: uuid.UUID) -> uuid.UUID:
    profile = db.get(BoardProfile, board_profile_id)
    owner = db.get(User, profile.user_id) if profile else None
    if profile is None or owner is None or owner.deleted_at is not None or profile.user_id == viewer_id:
        raise BoardError("프로필을 찾을 수 없어요.", "NOT_FOUND", 404)
    return profile.user_id


def block(db: Session, user_id: uuid.UUID, target_id: uuid.UUID) -> None:
    """차단 (소개팅과 같은 차단 목록을 쓴다). 그 사람과의 쪽지방도 닫는다."""
    exists = db.query(Block.id).filter(Block.blocker_user_id == user_id, Block.blocked_user_id == target_id).first()
    if exists is None:
        db.add(Block(blocker_user_id=user_id, blocked_user_id=target_id))
    close_rooms_between(db, user_id, target_id)


def close_rooms_between(db: Session, user_id: uuid.UUID, target_id: uuid.UUID) -> None:
    """차단하면 쪽지방을 닫는다 (소개팅 화면에서 차단해도)."""
    room = _room_between(db, user_id, target_id)
    if room is not None and room.closed_at is None:
        room.closed_at = utcnow()
        room.closed_by_user_id = user_id


# ---------- 글 · 댓글 ----------

def _visible_posts(db: Session, viewer_id: uuid.UUID):
    hidden_authors = blocked_ids(db, viewer_id)
    q = db.query(BoardPost).filter(BoardPost.deleted_at.is_(None), BoardPost.hidden_at.is_(None))
    if hidden_authors:
        q = q.filter(BoardPost.author_user_id.notin_(hidden_authors))
    return q


def list_posts(db: Session, viewer_id: uuid.UUID, board: str, before: datetime | None = None) -> list[BoardPost]:
    require_board(db, viewer_id, board)
    q = _visible_posts(db, viewer_id).filter(BoardPost.board == board)
    if before is not None:
        q = q.filter(BoardPost.created_at < before)
    return q.order_by(BoardPost.created_at.desc()).limit(PAGE_SIZE).all()


def _clean(text: str, max_len: int, what: str) -> str:
    value = (text or "").strip()
    if not value:
        raise BoardError(f"{what}을 적어 주세요.", "EMPTY", 422)
    if len(value) > max_len:
        raise BoardError(f"{what}은 {max_len:,}자까지 쓸 수 있어요.", "TOO_LONG", 422)
    return value


def create_post(db: Session, user: User, profile: BoardProfile, board: str, title: str, body: str) -> BoardPost:
    require_not_banned(profile)
    require_board(db, user.id, board)
    title = _clean(title, TITLE_MAX, "제목")
    body = _clean(body, BODY_MAX, "내용")
    today = db.query(func.count(BoardPost.id)).filter(
        BoardPost.author_user_id == user.id, BoardPost.created_at >= kst_day_start()
    ).scalar()
    if today >= DAILY_POSTS:
        raise BoardError(f"글은 하루 {DAILY_POSTS}개까지 쓸 수 있어요.", "DAILY_LIMIT", 429)
    post = BoardPost(author_user_id=user.id, board=board, title=title, body=body)
    db.add(post)
    db.flush()
    return post


def get_post(db: Session, viewer_id: uuid.UUID, post_id: uuid.UUID) -> BoardPost:
    post = db.get(BoardPost, post_id)
    if post is None or post.deleted_at is not None or post.author_user_id in blocked_ids(db, viewer_id):
        raise BoardError("글을 찾을 수 없어요.", "NOT_FOUND", 404)
    if post.hidden_at is not None and post.author_user_id != viewer_id:
        raise BoardError("신고로 숨겨진 글이에요.", "HIDDEN", 404)
    require_board(db, viewer_id, post.board)
    return post


def comments_of(db: Session, viewer_id: uuid.UUID, post_id: uuid.UUID) -> list[BoardComment]:
    hidden_authors = blocked_ids(db, viewer_id)
    q = db.query(BoardComment).filter(BoardComment.post_id == post_id, BoardComment.deleted_at.is_(None))
    if hidden_authors:
        q = q.filter(BoardComment.author_user_id.notin_(hidden_authors))
    rows = q.order_by(BoardComment.created_at).all()
    return [c for c in rows if c.hidden_at is None or c.author_user_id == viewer_id]


def create_comment(
    db: Session, user: User, profile: BoardProfile, post: BoardPost, body: str, reply_to_id: uuid.UUID | None = None
) -> BoardComment:
    """reply_to_id가 있으면 그 댓글에 다는 답글 (2026-11-22). 답글에 단 답글도 맨 위 댓글 밑에 붙는다."""
    require_not_banned(profile)
    body = _clean(body, COMMENT_MAX, "댓글")
    target: BoardComment | None = None
    if reply_to_id is not None:
        target = db.get(BoardComment, reply_to_id)
        if target is None or target.post_id != post.id or target.deleted_at is not None:
            raise BoardError("답글을 달 댓글을 찾을 수 없어요.", "NOT_FOUND", 404)
        if target.author_user_id in blocked_ids(db, user.id):
            raise BoardError("답글을 달 수 없는 댓글이에요.", "BLOCKED", 403)
    today = db.query(func.count(BoardComment.id)).filter(
        BoardComment.author_user_id == user.id, BoardComment.created_at >= kst_day_start()
    ).scalar()
    if today >= DAILY_COMMENTS:
        raise BoardError(f"댓글은 하루 {DAILY_COMMENTS}개까지 쓸 수 있어요.", "DAILY_LIMIT", 429)
    comment = BoardComment(
        post_id=post.id,
        author_user_id=user.id,
        body=body,
        parent_id=(target.parent_id or target.id) if target else None,
        reply_to_user_id=target.author_user_id if target else None,
    )
    db.add(comment)
    post.comment_count = (post.comment_count or 0) + 1
    db.flush()
    # 답글을 받은 사람에게 알림 (글쓴이와 같은 사람이면 아래 글쓴이 알림 하나만)
    if target is not None and target.author_user_id not in (user.id, post.author_user_id):
        notification_service.notify(
            db, target.author_user_id, "BOARD_COMMENT", "내 댓글에 답글이 달렸어요", post.title[:60], post.id
        )
        push_service.queue(db, target.author_user_id, push_service.BOARD_COMMENT, post.id)
    if post.author_user_id != user.id:
        notification_service.notify(
            db, post.author_user_id, "BOARD_COMMENT", "내 글에 댓글이 달렸어요", post.title[:60], post.id
        )
        push_service.queue(db, post.author_user_id, push_service.BOARD_COMMENT, post.id)
    return comment


def delete_post(post: BoardPost, *, admin_id: uuid.UUID | None = None) -> None:
    post.deleted_at = utcnow()
    post.deleted_by_admin_id = admin_id


def delete_comment(db: Session, comment: BoardComment, *, admin_id: uuid.UUID | None = None) -> None:
    if comment.deleted_at is None:
        post = db.get(BoardPost, comment.post_id)
        if post is not None and comment.hidden_at is None:
            post.comment_count = max(0, (post.comment_count or 0) - 1)
    comment.deleted_at = utcnow()
    comment.deleted_by_admin_id = admin_id


def post_view(post: BoardPost, authors: dict, viewer_id: uuid.UUID) -> dict:
    return {
        "id": str(post.id),
        "board": post.board,
        "title": post.title,
        "body": post.body,
        "author": authors.get(post.author_user_id),
        "mine": post.author_user_id == viewer_id,
        "hidden": post.hidden_at is not None,
        "comment_count": post.comment_count,
        "created_at": as_utc(post.created_at).isoformat(),
    }


def comment_view(comment: BoardComment, authors: dict, viewer_id: uuid.UUID, post_author_id: uuid.UUID) -> dict:
    return {
        "id": str(comment.id),
        "body": comment.body,
        "author": authors.get(comment.author_user_id),
        "mine": comment.author_user_id == viewer_id,
        "by_post_author": comment.author_user_id == post_author_id,
        "parent_id": str(comment.parent_id) if comment.parent_id else None,
        "reply_to": (authors.get(comment.reply_to_user_id) or {}).get("nickname") if comment.reply_to_user_id else None,
        "hidden": comment.hidden_at is not None,
        "created_at": as_utc(comment.created_at).isoformat(),
    }


# ---------- 신고 ----------

def _report_target(db: Session, target_type: str, target_id: uuid.UUID, reporter_id: uuid.UUID):
    """(대상 행, 신고당한 사람) — 신고할 수 없는 대상이면 오류."""
    if target_type == "POST":
        row = db.get(BoardPost, target_id)
        owner = row.author_user_id if row and row.deleted_at is None else None
    elif target_type == "COMMENT":
        row = db.get(BoardComment, target_id)
        owner = row.author_user_id if row and row.deleted_at is None else None
    elif target_type == "PROFILE":
        row = db.get(BoardProfile, target_id)
        owner = row.user_id if row else None
    elif target_type == "NOTE":
        row = db.get(NoteRoom, target_id)
        owner = None
        if row is not None and reporter_id in (row.starter_user_id, row.receiver_user_id):
            owner = row.receiver_user_id if reporter_id == row.starter_user_id else row.starter_user_id
    else:
        raise BoardError("신고할 수 없는 대상이에요.", "TARGET", 422)
    if owner is None or owner == reporter_id:
        raise BoardError("신고할 수 없는 대상이에요.", "NOT_FOUND", 404)
    return row, owner


def report(db: Session, reporter_id: uuid.UUID, target_type: str, target_id: uuid.UUID, reason: str,
           description: str | None) -> BoardReport:
    if target_type not in BOARD_REPORT_TARGETS or reason not in BOARD_REPORT_REASONS:
        raise BoardError("신고 사유를 다시 골라 주세요.", "REASON", 422)
    row, owner = _report_target(db, target_type, target_id, reporter_id)
    already = db.query(BoardReport.id).filter(
        BoardReport.reporter_user_id == reporter_id,
        BoardReport.target_type == target_type,
        BoardReport.target_id == target_id,
    ).first()
    if already is not None:
        raise BoardError("이미 신고했어요.", "ALREADY_REPORTED", 409)
    item = BoardReport(
        reporter_user_id=reporter_id, reported_user_id=owner, target_type=target_type, target_id=target_id,
        reason=reason, description=(description or "").strip()[:500] or None,
    )
    db.add(item)
    db.flush()
    count = db.query(func.count(BoardReport.id)).filter(
        BoardReport.target_type == target_type, BoardReport.target_id == target_id
    ).scalar()
    if count >= AUTO_HIDE_REPORTS:
        auto_hide(db, target_type, row)
    return item


def auto_hide(db: Session, target_type: str, row) -> None:
    """신고 3번 → 글·댓글 숨김, 프사 → 기본 그림. 쪽지는 관리자가 본다."""
    now = utcnow()
    if target_type == "POST" and row.hidden_at is None:
        row.hidden_at = now
    elif target_type == "COMMENT" and row.hidden_at is None:
        row.hidden_at = now
        post = db.get(BoardPost, row.post_id)
        if post is not None:
            post.comment_count = max(0, (post.comment_count or 0) - 1)
    elif target_type == "PROFILE" and row.avatar_key:
        clear_avatar(row)


def unhide(db: Session, target_type: str, row) -> None:
    if target_type == "COMMENT" and row.hidden_at is not None and row.deleted_at is None:
        post = db.get(BoardPost, row.post_id)
        if post is not None:
            post.comment_count = (post.comment_count or 0) + 1
    row.hidden_at = None


# ---------- 게시판 이용 정지 ----------

def ban(db: Session, profile: BoardProfile, days: int | None, reason: str) -> None:
    """days=None이면 영구. 사용자에게 알림을 보낸다. commit은 부르는 쪽에서."""
    profile.banned_until = PERMANENT_BAN if days is None else utcnow() + timedelta(days=days)
    profile.ban_reason = reason.strip()[:300]
    until = "영구" if days is None else f"{days}일"
    notification_service.notify(
        db, profile.user_id, "BOARD_BAN", "게시판 이용이 정지됐어요",
        f"운영 정책 위반으로 게시판 이용이 {until} 정지됐어요. 사유: {profile.ban_reason}", profile.id,
    )
    push_service.queue(db, profile.user_id, push_service.BOARD_BAN, profile.id)


def unban(db: Session, profile: BoardProfile) -> None:
    profile.banned_until = None
    profile.ban_reason = None
    notification_service.notify(
        db, profile.user_id, "BOARD_BAN", "게시판 이용 정지가 풀렸어요", "다시 글·댓글·쪽지를 쓸 수 있어요.", profile.id
    )
    push_service.queue(db, profile.user_id, push_service.BOARD_UNBAN, profile.id)


# ---------- 쪽지 ----------

def _room_between(db: Session, a: uuid.UUID, b: uuid.UUID) -> NoteRoom | None:
    return db.query(NoteRoom).filter(
        or_(
            (NoteRoom.starter_user_id == a) & (NoteRoom.receiver_user_id == b),
            (NoteRoom.starter_user_id == b) & (NoteRoom.receiver_user_id == a),
        )
    ).first()


def free_notes_left(db: Session, user: User) -> int | None:
    """여성 무료 쪽지가 오늘 몇 개 남았나. 무료 대상이 아니면 None."""
    if not vip_service.is_female_free(user):
        return None
    used = db.query(func.count(NoteRoom.id)).filter(
        NoteRoom.starter_user_id == user.id, NoteRoom.paid_with == "FREE", NoteRoom.created_at >= kst_day_start()
    ).scalar()
    return max(0, FEMALE_FREE_NOTES_PER_DAY - used)


def open_note(db: Session, user: User, profile: BoardProfile, target_id: uuid.UUID, body: str,
              post_id: uuid.UUID | None) -> tuple[NoteRoom, bool]:
    """게시판에서 쪽지 보내기. 이미 방이 있으면 그 방을 돌려준다 (돈 안 씀). (방, 새로 열었나)"""
    require_not_banned(profile)
    if target_id in blocked_ids(db, user.id):
        raise BoardError("쪽지를 보낼 수 없는 상대예요.", "BLOCKED", 403)
    target = db.get(User, target_id)
    if target is None or target.status != "ACTIVE" or get_profile(db, target_id) is None:
        raise BoardError("쪽지를 보낼 수 없는 상대예요.", "NOT_FOUND", 404)
    existing = _room_between(db, user.id, target_id)
    if existing is not None:
        if existing.closed_at is not None:
            raise BoardError("대화가 끝난 상대예요.", "CLOSED", 409)
        return existing, False
    body = _clean(body, NOTE_MAX, "쪽지")
    left = free_notes_left(db, user)
    if left is not None and left > 0:
        paid_with = "FREE"
    elif super_like_service.use_one(db, user):
        paid_with = "SUPER_LIKE"
    else:
        raise BoardError("슈퍼 라이크가 필요해요.", "NO_SUPER_LIKE", 402)
    now = utcnow()
    room = NoteRoom(starter_user_id=user.id, receiver_user_id=target_id, post_id=post_id, paid_with=paid_with,
                    starter_read_at=now, last_message_at=now)
    db.add(room)
    db.flush()
    db.add(NoteMessage(room_id=room.id, sender_user_id=user.id, body=body))
    _notify_note(db, target_id, room.id, first=True)
    return room, True


def _notify_note(db: Session, user_id: uuid.UUID, room_id: uuid.UUID, *, first: bool) -> None:
    if first:
        notification_service.notify(db, user_id, "NOTE", "새 쪽지가 왔어요", "게시판에서 누군가 쪽지를 보냈어요.", room_id)
    push_service.queue(db, user_id, push_service.NOTE, room_id)


def get_room(db: Session, user_id: uuid.UUID, room_id: uuid.UUID) -> NoteRoom:
    room = db.get(NoteRoom, room_id)
    if room is None or user_id not in (room.starter_user_id, room.receiver_user_id):
        raise BoardError("쪽지방을 찾을 수 없어요.", "NOT_FOUND", 404)
    return room


def partner_of(room: NoteRoom, user_id: uuid.UUID) -> uuid.UUID:
    return room.receiver_user_id if user_id == room.starter_user_id else room.starter_user_id


def waiting_reply(db: Session, room: NoteRoom) -> bool:
    """받은 사람이 아직 답장 안 함."""
    return db.query(NoteMessage.id).filter(
        NoteMessage.room_id == room.id, NoteMessage.sender_user_id == room.receiver_user_id
    ).first() is None


def can_send(db: Session, room: NoteRoom, user_id: uuid.UUID) -> tuple[bool, str | None]:
    if room.closed_at is not None:
        return False, "CLOSED"
    partner = db.get(User, partner_of(room, user_id))
    if partner is None or partner.status != "ACTIVE":
        return False, "PARTNER_GONE"
    if user_id == room.starter_user_id and waiting_reply(db, room):
        return False, "WAIT_REPLY"
    return True, None


def send_note(db: Session, user: User, profile: BoardProfile | None, room: NoteRoom, body: str) -> NoteMessage:
    # 받은 쪽지에 답장하는 건 정지 중에도 막는다 (정지 = 쪽지 보내기 금지)
    if profile is None:
        raise BoardError("게시판 프로필이 없어요.", "NO_BOARD_PROFILE", 403)
    require_not_banned(profile)
    ok, reason = can_send(db, room, user.id)
    if not ok:
        msg = {"CLOSED": "대화가 끝났어요.", "WAIT_REPLY": "상대가 답장하기 전에는 1개만 보낼 수 있어요.",
               "PARTNER_GONE": "상대가 떠났어요."}[reason]
        raise BoardError(msg, reason, 409)
    body = _clean(body, NOTE_MAX, "쪽지")
    message = NoteMessage(room_id=room.id, sender_user_id=user.id, body=body)
    db.add(message)
    now = utcnow()
    room.last_message_at = now
    mark_read(room, user.id, now)
    db.flush()
    _notify_note(db, partner_of(room, user.id), room.id, first=False)
    return message


def mark_read(room: NoteRoom, user_id: uuid.UUID, now: datetime | None = None) -> None:
    if user_id == room.starter_user_id:
        room.starter_read_at = now or utcnow()
    else:
        room.receiver_read_at = now or utcnow()


def leave(room: NoteRoom, user_id: uuid.UUID) -> None:
    if room.closed_at is None:
        room.closed_at = utcnow()
        room.closed_by_user_id = user_id


def rooms_of(db: Session, user_id: uuid.UUID) -> list[NoteRoom]:
    return db.query(NoteRoom).filter(
        or_(NoteRoom.starter_user_id == user_id, NoteRoom.receiver_user_id == user_id)
    ).order_by(NoteRoom.last_message_at.desc()).all()


def unread_count(db: Session, room: NoteRoom, user_id: uuid.UUID) -> int:
    read_at = room.starter_read_at if user_id == room.starter_user_id else room.receiver_read_at
    q = db.query(func.count(NoteMessage.id)).filter(NoteMessage.room_id == room.id, NoteMessage.sender_user_id != user_id)
    if read_at is not None:
        q = q.filter(NoteMessage.created_at > read_at)
    return q.scalar() or 0


def total_unread(db: Session, user_id: uuid.UUID) -> int:
    return sum(unread_count(db, r, user_id) for r in rooms_of(db, user_id))


def room_view(db: Session, room: NoteRoom, viewer_id: uuid.UUID, authors: dict | None = None) -> dict:
    partner_id = partner_of(room, viewer_id)
    authors = authors or public_views(db, {partner_id})
    last = db.query(NoteMessage).filter(NoteMessage.room_id == room.id).order_by(NoteMessage.created_at.desc()).first()
    ok, reason = can_send(db, room, viewer_id)
    return {
        "id": str(room.id),
        "partner": authors.get(partner_id),
        "i_started": viewer_id == room.starter_user_id,
        "closed": room.closed_at is not None,
        "can_send": ok,
        "cannot_send_reason": reason,
        "waiting_reply": waiting_reply(db, room),
        "unread": unread_count(db, room, viewer_id),
        "last_message": last.body[:80] if last else None,
        "last_message_mine": bool(last and last.sender_user_id == viewer_id),
        "last_message_at": as_utc(room.last_message_at).isoformat(),
    }


def config() -> dict:
    return {
        "sexual_rule": SEXUAL_RULE,
        "nickname_min": NICKNAME_MIN, "nickname_max": NICKNAME_MAX, "title_max": TITLE_MAX, "body_max": BODY_MAX,
        "comment_max": COMMENT_MAX, "note_max": NOTE_MAX, "daily_posts": DAILY_POSTS,
        "free_notes_per_day": FEMALE_FREE_NOTES_PER_DAY, "super_like_price": super_like_service.price(),
    }
