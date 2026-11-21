"""/api/v1 — 게시판(자유·연애·캐주얼)과 쪽지 (2026-11-22). 규칙은 app/services/board_service.py 맨 위."""

import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.rate_limit import enforce_rate_limit
from app.db.session import get_db
from app.deps import CurrentUser, get_current_user
from app.models.board import BoardComment, BoardPost, BoardProfile, NoteMessage
from app.schemas.board import (
    BoardBlock,
    BoardProfileCreate,
    BoardProfileUpdate,
    BoardReportCreate,
    CommentCreate,
    NoteOpen,
    NoteSend,
    PostCreate,
)
from app.services import admin_alert_service, board_service, super_like_service
from app.services.board_service import BoardError
from app.services.email_service import EmailService
from app.services.storage_service import PhotoValidationError, process_upload

router = APIRouter()

_NO_STORE = {"Cache-Control": "private, no-store"}


def _err(exc: BoardError) -> HTTPException:
    return HTTPException(status_code=exc.status, detail={"code": exc.code, "message": exc.message})


def _profile(db: Session, current: CurrentUser) -> BoardProfile:
    try:
        return board_service.require_profile(db, current.user)
    except BoardError as exc:
        raise _err(exc) from exc


# ---------- 게시판 프로필 ----------

@router.get("/board/me")
def board_me(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """게시판 탭을 열 때 처음 부른다. 프로필이 없으면 profile = null → '게시판 이용할래요?' 화면."""
    profile = board_service.get_profile(db, current.id)
    can_create, reason = board_service.can_create(db, current.user)
    return {
        "profile": board_service.own_view(db, current.user, profile) if profile else None,
        "can_create": can_create,
        "cannot_create_reason": reason,
        "boards": board_service.boards_view(db, current.id),
        "my_scores": board_service.my_scores(db, current.id),
        "score_labels": board_service.SCORE_LABELS,
        "free_notes_left": board_service.free_notes_left(db, current.user),
        "super_likes": super_like_service.view(current.user),
        "unread_notes": board_service.total_unread(db, current.id) if profile else 0,
        "config": board_service.config(),
    }


@router.post("/board/profile", status_code=status.HTTP_201_CREATED)
def create_board_profile(payload: BoardProfileCreate, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    enforce_rate_limit(f"board-profile:{current.id}", 20, 3600)
    try:
        profile = board_service.create_profile(db, current.user, payload.nickname, payload.shown_score)
    except BoardError as exc:
        raise _err(exc) from exc
    db.commit()
    return board_service.own_view(db, current.user, profile)


@router.patch("/board/profile")
def update_board_profile(payload: BoardProfileUpdate, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    enforce_rate_limit(f"board-profile:{current.id}", 20, 3600)
    profile = _profile(db, current)
    try:
        board_service.update_profile(
            db, profile, nickname=payload.nickname, shown_score=payload.shown_score, score_given=payload.change_score
        )
    except BoardError as exc:
        raise _err(exc) from exc
    db.commit()
    return board_service.own_view(db, current.user, profile)


@router.post("/board/profile/avatar")
def upload_avatar(file: UploadFile = File(...), current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """프사 직접 올리기. 검수 없이 바로 모두에게 보인다 (신고 3번이면 기본 그림으로)."""
    enforce_rate_limit(f"board-avatar:{current.id}", 10, 3600)
    profile = _profile(db, current)
    try:
        processed = process_upload(file, max_side=board_service.AVATAR_MAX_SIDE)
    except PhotoValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    board_service.set_avatar(db, profile, processed)
    db.commit()
    return board_service.own_view(db, current.user, profile)


@router.delete("/board/profile/avatar")
def delete_avatar(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = _profile(db, current)
    board_service.clear_avatar(profile)
    db.commit()
    return board_service.own_view(db, current.user, profile)


@router.get("/board/avatars/{board_profile_id}")
def get_avatar(board_profile_id: uuid.UUID, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """게시판 프로필이 있는 사람만 볼 수 있다."""
    _profile(db, current)
    target = db.get(BoardProfile, board_profile_id)
    data = board_service.read_avatar(target) if target else None
    if data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="프사가 없어요.")
    return Response(content=data, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})


@router.get("/board/profiles/{board_profile_id}")
def get_board_profile(board_profile_id: uuid.UUID, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """작성자를 눌렀을 때 보이는 작은 카드 (게시판 프로필만. 소개팅 프로필은 절대 안 보임)."""
    _profile(db, current)
    try:
        owner = board_service.profile_owner(db, board_profile_id, current.id)
    except BoardError as exc:
        raise _err(exc) from exc
    if owner in board_service.blocked_ids(db, current.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="프로필을 찾을 수 없어요.")
    room = board_service._room_between(db, current.id, owner)
    return {
        "profile": board_service.public_views(db, {owner})[owner],
        "note_room_id": str(room.id) if room else None,
        "note_room_closed": bool(room and room.closed_at),
    }


# ---------- 글 · 댓글 ----------

def _post_list_item(post: BoardPost, authors: dict, me: uuid.UUID) -> dict:
    view = board_service.post_view(post, authors, me)
    view["body"] = post.body[:120]
    return view


@router.get("/board/posts")
def list_posts(
    board: str = Query(default="FREE"),
    before: datetime | None = None,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _profile(db, current)
    try:
        posts = board_service.list_posts(db, current.id, board, before)
    except BoardError as exc:
        raise _err(exc) from exc
    authors = board_service.public_views(db, {p.author_user_id for p in posts})
    return {
        "posts": [_post_list_item(p, authors, current.id) for p in posts],
        "has_more": len(posts) == board_service.PAGE_SIZE,
    }


@router.post("/board/posts", status_code=status.HTTP_201_CREATED)
def create_post(payload: PostCreate, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    enforce_rate_limit(f"board-post:{current.id}", 20, 3600)
    profile = _profile(db, current)
    try:
        post = board_service.create_post(db, current.user, profile, payload.board, payload.title, payload.body)
    except BoardError as exc:
        raise _err(exc) from exc
    db.commit()
    return board_service.post_view(post, board_service.public_views(db, {current.id}), current.id)


@router.get("/board/posts/{post_id}")
def get_post(post_id: uuid.UUID, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    _profile(db, current)
    try:
        post = board_service.get_post(db, current.id, post_id)
    except BoardError as exc:
        raise _err(exc) from exc
    comments = board_service.comments_of(db, current.id, post.id)
    people = {post.author_user_id} | {c.author_user_id for c in comments} | {c.reply_to_user_id for c in comments if c.reply_to_user_id}
    authors = board_service.public_views(db, people)
    return {
        "post": board_service.post_view(post, authors, current.id),
        "comments": [board_service.comment_view(c, authors, current.id, post.author_user_id) for c in comments],
    }


@router.delete("/board/posts/{post_id}")
def delete_post(post_id: uuid.UUID, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    post = db.get(BoardPost, post_id)
    if post is None or post.author_user_id != current.id or post.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="글을 찾을 수 없어요.")
    board_service.delete_post(post)
    db.commit()
    return {"deleted": True}


@router.post("/board/posts/{post_id}/comments", status_code=status.HTTP_201_CREATED)
def create_comment(post_id: uuid.UUID, payload: CommentCreate, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    enforce_rate_limit(f"board-comment:{current.id}", 60, 3600)
    profile = _profile(db, current)
    try:
        post = board_service.get_post(db, current.id, post_id)
        comment = board_service.create_comment(db, current.user, profile, post, payload.body, payload.reply_to_id)
    except BoardError as exc:
        raise _err(exc) from exc
    db.commit()
    authors = board_service.public_views(db, {current.id} | ({comment.reply_to_user_id} if comment.reply_to_user_id else set()))
    return board_service.comment_view(comment, authors, current.id, post.author_user_id)


@router.delete("/board/comments/{comment_id}")
def delete_comment(comment_id: uuid.UUID, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    comment = db.get(BoardComment, comment_id)
    if comment is None or comment.author_user_id != current.id or comment.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="댓글을 찾을 수 없어요.")
    board_service.delete_comment(db, comment)
    db.commit()
    return {"deleted": True}


# ---------- 신고 · 차단 ----------

@router.post("/board/reports", status_code=status.HTTP_201_CREATED)
def report(payload: BoardReportCreate, background: BackgroundTasks, current: CurrentUser = Depends(get_current_user),
           db: Session = Depends(get_db)):
    enforce_rate_limit(f"board-report:{current.id}", 20, 3600)
    try:
        item = board_service.report(db, current.id, payload.target_type, payload.target_id, payload.reason, payload.description)
    except BoardError as exc:
        raise _err(exc) from exc
    db.commit()
    recipients = admin_alert_service.admin_emails_with(db, "reports:update")
    background.add_task(admin_alert_service.send_all, EmailService.send_admin_new_board_report, recipients, payload.reason)
    return {"report_id": str(item.id)}


@router.post("/board/blocks", status_code=status.HTTP_201_CREATED)
def block(payload: BoardBlock, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """게시판에서 차단. 소개팅 차단 목록과 같다 (서로 추천·게시판·쪽지 모두 안 보임)."""
    enforce_rate_limit(f"block:{current.id}", 30, 3600)
    try:
        target = board_service.profile_owner(db, payload.board_profile_id, current.id)
    except BoardError as exc:
        raise _err(exc) from exc
    board_service.block(db, current.id, target)
    db.commit()
    return {"blocked": True}


# ---------- 쪽지 ----------

@router.get("/notes")
def list_notes(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    rooms = board_service.rooms_of(db, current.id)
    hidden = board_service.blocked_ids(db, current.id)
    rooms = [r for r in rooms if board_service.partner_of(r, current.id) not in hidden]
    authors = board_service.public_views(db, {board_service.partner_of(r, current.id) for r in rooms})
    return {"rooms": [board_service.room_view(db, r, current.id, authors) for r in rooms]}


@router.post("/notes", status_code=status.HTTP_201_CREATED)
def open_note(payload: NoteOpen, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """게시판에서 쪽지 보내기 (슈퍼 라이크 1개, 여성은 하루 3개 무료). 이미 방이 있으면 그 방으로 (new=false)."""
    enforce_rate_limit(f"note-open:{current.id}", 30, 3600)
    profile = _profile(db, current)
    try:
        target = board_service.profile_owner(db, payload.board_profile_id, current.id)
        room, new = board_service.open_note(db, current.user, profile, target, payload.body, payload.post_id)
    except BoardError as exc:
        raise _err(exc) from exc
    db.commit()
    return {"room": board_service.room_view(db, room, current.id), "new": new}


def _message_view(m: NoteMessage, me: uuid.UUID) -> dict:
    return {"id": str(m.id), "body": m.body, "mine": m.sender_user_id == me, "created_at": m.created_at.isoformat()}


@router.get("/notes/{room_id}")
def get_note_room(room_id: uuid.UUID, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        room = board_service.get_room(db, current.id, room_id)
    except BoardError as exc:
        raise _err(exc) from exc
    messages = db.query(NoteMessage).filter(NoteMessage.room_id == room.id).order_by(NoteMessage.created_at).all()
    board_service.mark_read(room, current.id)
    db.commit()
    return {
        "room": board_service.room_view(db, room, current.id),
        "messages": [_message_view(m, current.id) for m in messages],
    }


@router.post("/notes/{room_id}/messages", status_code=status.HTTP_201_CREATED)
def send_note(room_id: uuid.UUID, payload: NoteSend, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    enforce_rate_limit(f"note-send:{current.id}", 120, 3600)
    try:
        room = board_service.get_room(db, current.id, room_id)
        message = board_service.send_note(db, current.user, board_service.get_profile(db, current.id), room, payload.body)
    except BoardError as exc:
        raise _err(exc) from exc
    db.commit()
    return _message_view(message, current.id)


@router.post("/notes/{room_id}/leave")
def leave_note(room_id: uuid.UUID, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        room = board_service.get_room(db, current.id, room_id)
    except BoardError as exc:
        raise _err(exc) from exc
    board_service.leave(room, current.id)
    db.commit()
    return {"closed": True}
