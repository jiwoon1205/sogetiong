import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, Uuid, false, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models._common import created_at, pk, updated_at


class User(Base):
    """계정. status: PENDING / ACTIVE / SUSPENDED / BANNED / DELETED (설계도 §61).

    email_hash: 학교 이메일의 지문(HMAC). 탈퇴하면 email은 가짜 주소로 바뀌고 이 값만 남는다.
    같은 사람이 다시 가입했는지 알아보는 데만 쓴다 (정지된 사람 재가입 차단, 차단 기록 이어받기).
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = pk()
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    email_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    university_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("universities.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 마지막 접속 (관리자 확인용). 로그인할 때, 그리고 사이트를 쓰는 동안 10분에 한 번씩 기록한다.
    # 세션은 로그아웃하면 지워지므로 여기에 따로 남긴다.
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 탈퇴할 때 지워지는 공개 프로필에서 닉네임·성별만 관리자용으로 남긴다 (2026-10-01, 마이그레이션 0012).
    # 이게 없으면 관리자 화면에서 닉네임 검색·성별 필터로 탈퇴한 사람을 찾을 수 없다.
    deleted_nickname: Mapped[str | None] = mapped_column(String(40), nullable=True)
    deleted_gender: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # 가입비 (2026-10-03, 마이그레이션 0014)
    # is_beta_member: 유료화(MEMBERSHIP_ENABLED)를 켜기 전에 가입한 사람 (기록용, 2026-10-04부터 결제 면제 아님)
    # signup_paid_at: 첫 이용권 입금을 확인한 시각 (기록용. 첫 이용권을 환불하면 다시 비운다)
    is_beta_member: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true(), nullable=False)
    signup_paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # VIP가 끝나는 시각 (2026-10-03, 마이그레이션 0015). 이 시각이 지금보다 뒤면 VIP다.
    vip_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 이용권 (2026-10-04 구독제, 마이그레이션 0016). 계산은 services/membership_service.py에만 있다.
    # member_until: 이용권(기본·VIP 포함)이 끝나는 시각. 지금보다 뒤면 추천을 볼 수 있다. VIP를 사면 이것도 늘어난다.
    # member_days_banked: 아직 시작하지 않은 이용권 일수. 사진 검수 전에 낸 첫 이용권은 여기에 쌓아 두고,
    #   등급이 정해져 추천이 열리는 순간부터 센다.
    # ※ is_beta_member·signup_paid_at은 2026-10-04부터 결제 판단에 쓰지 않는다 (기록용). 베타 회원도 이용권이 필요하다.
    member_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    member_days_banked: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    # 매칭 정지 (2026-10-05, 마이그레이션 0017). 관리자만 켜고 끈다. 본인에게는 절대 알려주지 않는다.
    # 켜져 있으면: 서로 LIKE해도 매칭이 "숨김(HIDDEN)"으로 만들어져 두 사람 모두에게 보이지 않는다.
    # 정지를 풀어도 숨겨진 매칭은 그대로 숨김이다 → 관리자가 하나씩 골라서 다시 보이게 한다.
    match_suspended: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    match_suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 휴대폰 알림을 못 받을 때(알림을 안 켰거나 배달 실패) 새 메시지·새 매칭을 학교 메일로 알려줄지
    # (2026-10-05, 마이그레이션 0019). 본인이 설정 화면에서 끌 수 있다.
    email_notify: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true(), nullable=False)
    # 한 번만 보여주는 공지 팝업에서 마지막으로 "확인"을 누른 공지 이름 (2026-10-05, 마이그레이션 0020)
    # → services/announcement_service.py
    announcement_seen: Mapped[str | None] = mapped_column(String(60), nullable=True)
    # 무료 체험 (2026-10-06, 마이그레이션 0021). 계산은 services/membership_service.py에 있다.
    # trial_likes_used: 체험으로 보낸 LIKE 수 (평생, 다시 줄지 않음). 이용권을 사면 체험 끝 → FREE_TRIAL_LIKES 이상으로 채운다.
    #   탈퇴해도 이 줄은 남고, 재가입하면 이어받는다 (auth_service.carry_over_account).
    # rereview_granted_at: 이용권·VIP를 산 시각 = "사진 바로 재검토 1회" 혜택을 받은 시각.
    #   이 시각 뒤에 그 혜택으로 낸 사진이 승인되면 사용한 것 (사면 다시 1회로 채워짐, 쌓이지 않음)
    trial_likes_used: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    rereview_granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 관리자가 준 "오늘만" 추가 좋아요 (2026-10-10, 마이그레이션 0023). bonus_likes_date가 오늘(한국 시간)일 때만 하루 한도에 더한다.
    # 날짜가 지나면 저절로 무시된다 (지우지 않아도 됨). 계산은 vip_service.daily_like_limit
    bonus_likes: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    bonus_likes_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    public_profile = relationship("PublicProfile", back_populates="user", uselist=False)
    private_profile = relationship("PrivateProfile", back_populates="user", uselist=False)


class UserDailyVisit(Base):
    """하루 접속 기록 (2026-10-01). 한 사람이 하루(한국 시간)에 한 줄만 쌓인다.

    - 추천 순서의 "활동 점수": 최근 14일 중 며칠 접속했나
    - 관리자 대시보드의 "활성 사용자": 최근 7일 안에 접속한 사람 수
    """

    __tablename__ = "user_daily_visits"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    visit_date: Mapped[date] = mapped_column(Date, primary_key=True, index=True)


class UserSession(Base):
    """로그인 세션. 브라우저 쿠키에는 원문, DB에는 해시만 저장한다."""

    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    csrf_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = created_at()


class VerificationToken(Base):
    """이메일 인증번호.

    purpose=SIGNUP: 학교 이메일 인증 → 가입용 1회 티켓 발급
    purpose=PASSWORD_RESET: 비밀번호 재설정 코드
    용도가 다른 코드는 서로 쓸 수 없다.
    """

    __tablename__ = "verification_tokens"

    id: Mapped[uuid.UUID] = pk()
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(20), default="SIGNUP", server_default="SIGNUP", nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ticket_hash: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    ticket_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = created_at()
