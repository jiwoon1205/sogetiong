"""자유게시판 · 쪽지 (2026-11-22, 프로젝트 문서 `자유게시판·쪽지 설계 (2026-11-22)`).

규칙은 app/services/board_service.py 맨 위 설명.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.core.time import utcnow
from app.models._common import created_at, pk, updated_at

# 게시판에 공개할 수 있는 점수 (AppearanceEvaluation 칸 이름과 같다)
SCORE_KEYS = ("overall_impression", "style", "grooming", "photo_vibe")

# 게시판 3개 (2026-11-22 추가). 연애·캐주얼은 "찾는 관계"가 맞는 사람만 보고 쓸 수 있다.
BOARDS = ("FREE", "LOVE", "CASUAL")
BOARD_REQUIRED_GOAL = {"LOVE": "SERIOUS", "CASUAL": "CASUAL"}

# 신고할 수 있는 것
BOARD_REPORT_TARGETS = ("POST", "COMMENT", "PROFILE", "NOTE")
BOARD_REPORT_REASONS = (
    "ABUSE",  # 욕설·비하
    "SEXUAL",  # 성적인 이야기 (캐주얼 게시판 밖에서는 정지 사유)
    "OBSCENE",  # 음란·부적절한 사진
    "SPAM",  # 광고·도배
    "PERSONAL_INFO",  # 개인정보 노출
    "OTHER",  # 기타 (직접 쓰기)
)


class BoardProfile(Base):
    """게시판 전용 프로필. 소개팅 프로필(public_profiles)과 완전히 따로다.
    다른 사용자에게는 닉네임·프사·성별·학교(캠퍼스)·(고른 경우) 점수 1개만 보인다."""

    __tablename__ = "board_profiles"

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), unique=True, nullable=False)
    nickname: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    nickname_changed_at: Mapped[datetime] = created_at()
    # 직접 올린 프사 파일. 없으면 기본 그림. 검수 없이 바로 보인다 (신고 3번이면 지움)
    avatar_key: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # 공개한 점수 칸 (SCORE_KEYS 중 하나). 없으면 공개 안 함
    shown_score: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # 게시판 이용 정지 (관리자). 이 시각까지 글·댓글·쪽지 보내기 금지. 영구 정지는 아주 먼 날짜
    banned_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ban_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()


class BoardPost(Base):
    __tablename__ = "board_posts"

    id: Mapped[uuid.UUID] = pk()
    author_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    # 어느 게시판 글인지 (BOARDS 중 하나)
    board: Mapped[str] = mapped_column(String(10), default="FREE", server_default="FREE", nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(40), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    comment_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    # 신고 3번으로 자동 숨김된 시각 (관리자가 풀 수 있음)
    hidden_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 지운 시각 (본인 또는 관리자). 지운 글은 사용자에게 안 보이고, 관리자 확인용으로 내용은 남긴다
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("admin_users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)


class BoardComment(Base):
    __tablename__ = "board_comments"

    id: Mapped[uuid.UUID] = pk()
    post_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("board_posts.id"), nullable=False, index=True)
    author_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    hidden_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("admin_users.id"), nullable=True)
    created_at: Mapped[datetime] = created_at()


class BoardReport(Base):
    """게시판 신고. 같은 사람이 같은 대상을 두 번 신고할 수 없다.
    status: OPEN / RESOLVED (관리자가 처리) / DISMISSED (문제 없음)"""

    __tablename__ = "board_reports"
    __table_args__ = (UniqueConstraint("reporter_user_id", "target_type", "target_id", name="uq_board_report_once"),)

    id: Mapped[uuid.UUID] = pk()
    reporter_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    reported_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(10), nullable=False)  # BOARD_REPORT_TARGETS
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(20), nullable=False)  # BOARD_REPORT_REASONS
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="OPEN", nullable=False, index=True)
    created_at: Mapped[datetime] = created_at()
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class NoteRoom(Base):
    """쪽지방. 매칭 대화방(matches)과 따로다. 두 사람 사이에 하나만 (먼저 보낸 사람 = starter).
    starter가 쪽지를 열 때 슈퍼 라이크 1개를 쓴다 (여성은 하루 3개까지 무료)."""

    __tablename__ = "note_rooms"

    id: Mapped[uuid.UUID] = pk()
    starter_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    receiver_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    post_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("board_posts.id"), nullable=True)
    paid_with: Mapped[str] = mapped_column(String(12), nullable=False)  # SUPER_LIKE / FREE
    # 누군가 나가면(또는 차단) 닫힌다. 닫힌 방에는 더 못 보낸다
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    starter_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    receiver_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_message_at: Mapped[datetime] = created_at()
    created_at: Mapped[datetime] = created_at()


class NoteMessage(Base):
    __tablename__ = "note_messages"

    id: Mapped[uuid.UUID] = pk()
    room_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("note_rooms.id"), nullable=False, index=True)
    sender_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = created_at()
