"""/api/v1/admin/board — 게시판 신고 처리 · 즉시 삭제 · 이용 정지 (2026-11-22).

권한
- 보기: reports:read · 지우기/숨김 풀기/프사 지우기/신고 처리: reports:update
- 게시판 이용 정지·해제: users:status · 쪽지 내용 보기(쪽지 신고): chats:read (열 때마다 감사 로그)
모든 조치는 감사 로그에 남긴다 (BOARD_DELETE, BOARD_UNHIDE, BOARD_AVATAR_RESET, BOARD_BAN, BOARD_UNBAN, NOTE_VIEW).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.time import as_utc, utcnow
from app.db.session import get_db
from app.deps import CurrentAdmin, require_permission
from app.models.board import BOARDS, BoardComment, BoardPost, BoardProfile, BoardReport, NoteMessage, NoteRoom
from app.models.user import User
from app.schemas.board import BoardBan, BoardReportResolve
from app.services import audit_service, board_service
from app.services.email_service import BOARD_REPORT_REASON_LABELS

router = APIRouter()


def _iso(value) -> str | None:
    return as_utc(value).isoformat() if value else None


def _admin_profile_view(db: Session, user_id: uuid.UUID) -> dict:
    view = board_service.public_views(db, {user_id})[user_id]
    profile = board_service.get_profile(db, user_id)
    user = db.get(User, user_id)
    view.update(
        {
            "user_id": str(user_id),
            "dating_nickname": user.public_profile.nickname if user and user.public_profile else None,
            "banned_until": _iso(profile.banned_until) if profile and board_service.is_banned(profile) else None,
            "ban_permanent": bool(profile and board_service.is_banned(profile) and as_utc(profile.banned_until).year >= 2999),
            "ban_reason": profile.ban_reason if profile and board_service.is_banned(profile) else None,
        }
    )
    return view


def _post_admin_view(post: BoardPost, authors: dict) -> dict:
    return {
        "id": str(post.id),
        "board": post.board,
        "title": post.title,
        "body": post.body,
        "author": authors.get(post.author_user_id),
        "author_user_id": str(post.author_user_id),
        "comment_count": post.comment_count,
        "hidden": post.hidden_at is not None,
        "deleted": post.deleted_at is not None,
        "created_at": _iso(post.created_at),
    }


def _comment_admin_view(c: BoardComment, authors: dict) -> dict:
    return {
        "id": str(c.id),
        "post_id": str(c.post_id),
        "parent_id": str(c.parent_id) if c.parent_id else None,
        "body": c.body,
        "author": authors.get(c.author_user_id),
        "author_user_id": str(c.author_user_id),
        "hidden": c.hidden_at is not None,
        "deleted": c.deleted_at is not None,
        "created_at": _iso(c.created_at),
    }


def _target_preview(db: Session, r: BoardReport) -> dict:
    if r.target_type == "POST":
        p = db.get(BoardPost, r.target_id)
        return {"board": p.board, "title": p.title, "text": p.body[:300], "hidden": p.hidden_at is not None,
                "deleted": p.deleted_at is not None, "post_id": str(p.id)} if p else {}
    if r.target_type == "COMMENT":
        c = db.get(BoardComment, r.target_id)
        post = db.get(BoardPost, c.post_id) if c else None
        return {"board": post.board if post else None, "text": c.body[:300], "hidden": c.hidden_at is not None,
                "deleted": c.deleted_at is not None, "post_id": str(c.post_id)} if c else {}
    if r.target_type == "PROFILE":
        p = db.get(BoardProfile, r.target_id)
        return {"text": p.nickname if p else "", "has_avatar": bool(p and p.avatar_key)}
    return {"note_room_id": str(r.target_id)}


# ---------- 신고 ----------

@router.get("/board/reports")
def list_reports(
    status_filter: str = Query(default="OPEN", alias="status"),
    admin: CurrentAdmin = Depends(require_permission("reports:read")),
    db: Session = Depends(get_db),
):
    q = db.query(BoardReport)
    if status_filter != "ALL":
        q = q.filter(BoardReport.status == status_filter)
    rows = q.order_by(BoardReport.created_at.desc()).limit(200).all()
    counts = dict(
        db.query(BoardReport.target_id, func.count(BoardReport.id)).filter(
            BoardReport.target_id.in_([r.target_id for r in rows])
        ).group_by(BoardReport.target_id).all()
    ) if rows else {}
    reported = {r.reported_user_id for r in rows}
    return {
        "reports": [
            {
                "id": str(r.id),
                "target_type": r.target_type,
                "target_id": str(r.target_id),
                "reason": r.reason,
                "reason_label": BOARD_REPORT_REASON_LABELS.get(r.reason, r.reason),
                "description": r.description,
                "status": r.status,
                "created_at": _iso(r.created_at),
                "reports_on_target": counts.get(r.target_id, 1),
                "reported": _admin_profile_view(db, r.reported_user_id),
                "target": _target_preview(db, r),
            }
            for r in rows
        ],
        "reported_users": len(reported),
    }


@router.post("/board/reports/{report_id}")
def resolve_report(
    report_id: uuid.UUID,
    payload: BoardReportResolve,
    request: Request,
    admin: CurrentAdmin = Depends(require_permission("reports:update")),
    db: Session = Depends(get_db),
):
    if payload.status not in ("RESOLVED", "DISMISSED"):
        raise HTTPException(status_code=422, detail="처리 결과를 골라 주세요.")
    item = db.get(BoardReport, report_id)
    if item is None:
        raise HTTPException(status_code=404, detail="신고를 찾을 수 없어요.")
    # 같은 대상에 대한 열린 신고를 한꺼번에 처리
    db.query(BoardReport).filter(
        BoardReport.target_type == item.target_type, BoardReport.target_id == item.target_id, BoardReport.status == "OPEN"
    ).update({"status": payload.status, "resolved_at": utcnow()}, synchronize_session=False)
    audit_service.record(db, admin_id=admin.id, action=f"BOARD_REPORT_{payload.status}", target_type="BOARD_REPORT",
                         target_id=item.id, request=request)
    db.commit()
    return {"status": payload.status}


# ---------- 글 · 댓글 ----------

@router.get("/board/posts")
def list_posts(
    board: str | None = None,
    admin: CurrentAdmin = Depends(require_permission("reports:read")),
    db: Session = Depends(get_db),
):
    """최근 글 (숨김·삭제 포함). 신고 없이도 바로 지울 수 있게."""
    q = db.query(BoardPost)
    if board in BOARDS:
        q = q.filter(BoardPost.board == board)
    posts = q.order_by(BoardPost.created_at.desc()).limit(100).all()
    authors = board_service.public_views(db, {p.author_user_id for p in posts})
    return {"posts": [_post_admin_view(p, authors) for p in posts]}


@router.get("/board/posts/{post_id}")
def get_post(post_id: uuid.UUID, admin: CurrentAdmin = Depends(require_permission("reports:read")), db: Session = Depends(get_db)):
    post = db.get(BoardPost, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="글을 찾을 수 없어요.")
    comments = db.query(BoardComment).filter(BoardComment.post_id == post.id).order_by(BoardComment.created_at).all()
    authors = board_service.public_views(db, {post.author_user_id} | {c.author_user_id for c in comments})
    return {"post": _post_admin_view(post, authors), "comments": [_comment_admin_view(c, authors) for c in comments]}


@router.delete("/board/posts/{post_id}")
def delete_post(post_id: uuid.UUID, request: Request, admin: CurrentAdmin = Depends(require_permission("reports:update")),
                db: Session = Depends(get_db)):
    post = db.get(BoardPost, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="글을 찾을 수 없어요.")
    if post.deleted_at is None:
        board_service.delete_post(post, admin_id=admin.id)
    audit_service.record(db, admin_id=admin.id, action="BOARD_DELETE", target_type="BOARD_POST", target_id=post.id, request=request)
    db.commit()
    return {"deleted": True}


@router.delete("/board/comments/{comment_id}")
def delete_comment(comment_id: uuid.UUID, request: Request, admin: CurrentAdmin = Depends(require_permission("reports:update")),
                   db: Session = Depends(get_db)):
    comment = db.get(BoardComment, comment_id)
    if comment is None:
        raise HTTPException(status_code=404, detail="댓글을 찾을 수 없어요.")
    if comment.deleted_at is None:
        board_service.delete_comment(db, comment, admin_id=admin.id)
    audit_service.record(db, admin_id=admin.id, action="BOARD_DELETE", target_type="BOARD_COMMENT", target_id=comment.id, request=request)
    db.commit()
    return {"deleted": True}


@router.post("/board/{kind}/{target_id}/unhide")
def unhide(kind: str, target_id: uuid.UUID, request: Request, admin: CurrentAdmin = Depends(require_permission("reports:update")),
           db: Session = Depends(get_db)):
    """신고 3번으로 자동 숨김된 글·댓글을 다시 보이게 (잘못 신고된 경우)."""
    model = {"posts": BoardPost, "comments": BoardComment}.get(kind)
    row = db.get(model, target_id) if model else None
    if row is None:
        raise HTTPException(status_code=404, detail="찾을 수 없어요.")
    board_service.unhide(db, "POST" if model is BoardPost else "COMMENT", row)
    audit_service.record(db, admin_id=admin.id, action="BOARD_UNHIDE", target_type=f"BOARD_{kind.upper()[:-1]}", target_id=row.id,
                         request=request)
    db.commit()
    return {"hidden": False}


# ---------- 게시판 프로필 · 이용 정지 ----------

def _board_profile(db: Session, board_profile_id: uuid.UUID) -> BoardProfile:
    profile = db.get(BoardProfile, board_profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="게시판 프로필을 찾을 수 없어요.")
    return profile


@router.get("/board/profiles/{board_profile_id}")
def profile_activity(board_profile_id: uuid.UUID, admin: CurrentAdmin = Depends(require_permission("reports:read")),
                     db: Session = Depends(get_db)):
    """한 사람의 게시판 활동: 프로필, 최근 글·댓글, 받은 신고."""
    profile = _board_profile(db, board_profile_id)
    uid = profile.user_id
    posts = db.query(BoardPost).filter(BoardPost.author_user_id == uid).order_by(BoardPost.created_at.desc()).limit(50).all()
    comments = db.query(BoardComment).filter(BoardComment.author_user_id == uid).order_by(BoardComment.created_at.desc()).limit(50).all()
    reports = db.query(BoardReport).filter(BoardReport.reported_user_id == uid).order_by(BoardReport.created_at.desc()).limit(50).all()
    authors = board_service.public_views(db, {uid})
    return {
        "profile": _admin_profile_view(db, uid),
        "posts": [_post_admin_view(p, authors) for p in posts],
        "comments": [_comment_admin_view(c, authors) for c in comments],
        "reports": [
            {"id": str(r.id), "target_type": r.target_type, "reason_label": BOARD_REPORT_REASON_LABELS.get(r.reason, r.reason),
             "status": r.status, "created_at": _iso(r.created_at)}
            for r in reports
        ],
    }


@router.get("/board/avatars/{board_profile_id}")
def avatar(board_profile_id: uuid.UUID, admin: CurrentAdmin = Depends(require_permission("reports:read")), db: Session = Depends(get_db)):
    data = board_service.read_avatar(_board_profile(db, board_profile_id))
    if data is None:
        raise HTTPException(status_code=404, detail="프사가 없어요.")
    return Response(content=data, media_type="image/jpeg", headers={"Cache-Control": "no-store, private"})


@router.post("/board/profiles/{board_profile_id}/reset-avatar")
def reset_avatar(board_profile_id: uuid.UUID, request: Request, admin: CurrentAdmin = Depends(require_permission("reports:update")),
                 db: Session = Depends(get_db)):
    profile = _board_profile(db, board_profile_id)
    board_service.clear_avatar(profile)
    audit_service.record(db, admin_id=admin.id, action="BOARD_AVATAR_RESET", target_type="BOARD_PROFILE", target_id=profile.id,
                         request=request)
    db.commit()
    return {"has_avatar": False}


@router.post("/board/profiles/{board_profile_id}/ban")
def ban(board_profile_id: uuid.UUID, payload: BoardBan, request: Request,
        admin: CurrentAdmin = Depends(require_permission("users:status")), db: Session = Depends(get_db)):
    """게시판 이용 정지 (7일 / 30일 / 영구). 사용자에게 앱 알림 + 휴대폰 알림(안 되면 메일)."""
    if payload.days not in (None, 1, 3, 7, 30):
        raise HTTPException(status_code=422, detail="정지 기간을 골라 주세요.")
    profile = _board_profile(db, board_profile_id)
    board_service.ban(db, profile, payload.days, payload.reason)
    audit_service.record(db, admin_id=admin.id, action="BOARD_BAN", target_type="BOARD_PROFILE", target_id=profile.id,
                         request=request, metadata={"days": payload.days})
    db.commit()
    return _admin_profile_view(db, profile.user_id)


@router.post("/board/profiles/{board_profile_id}/unban")
def unban(board_profile_id: uuid.UUID, request: Request, admin: CurrentAdmin = Depends(require_permission("users:status")),
          db: Session = Depends(get_db)):
    profile = _board_profile(db, board_profile_id)
    board_service.unban(db, profile)
    audit_service.record(db, admin_id=admin.id, action="BOARD_UNBAN", target_type="BOARD_PROFILE", target_id=profile.id, request=request)
    db.commit()
    return _admin_profile_view(db, profile.user_id)


# ---------- 쪽지 신고 확인 ----------

@router.get("/board/notes/{room_id}")
def note_room(room_id: uuid.UUID, request: Request, admin: CurrentAdmin = Depends(require_permission("chats:read")),
              db: Session = Depends(get_db)):
    room = db.get(NoteRoom, room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="쪽지방을 찾을 수 없어요.")
    messages = db.query(NoteMessage).filter(NoteMessage.room_id == room.id).order_by(NoteMessage.created_at).all()
    people = board_service.public_views(db, {room.starter_user_id, room.receiver_user_id})
    audit_service.record(db, admin_id=admin.id, action="NOTE_VIEW", target_type="NOTE_ROOM", target_id=room.id, request=request)
    db.commit()
    return {
        "starter": people[room.starter_user_id],
        "receiver": people[room.receiver_user_id],
        "closed": room.closed_at is not None,
        "messages": [
            {"from": "STARTER" if m.sender_user_id == room.starter_user_id else "RECEIVER", "body": m.body,
             "created_at": _iso(m.created_at)}
            for m in messages
        ],
    }
