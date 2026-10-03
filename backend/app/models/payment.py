import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._common import created_at, pk

# 결제 상태 (2026-10-03, 운영자 통장 직접 입금 방식)
#   CREATED   : 결제 코드만 받음 (아직 "입금했어요"를 안 누름) → 관리자 목록에 안 나온다
#   REQUESTED : "입금했어요"를 누름 → 관리자 "확인 대기" 목록
#   CONFIRMED : 관리자가 통장에서 입금을 확인함 → 사진 제출이 열린다
#   REJECTED  : 관리자가 "입금 없음"으로 처리 → 사용자가 다시 "입금했어요"를 누를 수 있다
#   REFUNDED  : 환불함 (사진 검수 전에만 가능) → 다시 입금 전 상태가 된다
PAYMENT_STATUSES = ("CREATED", "REQUESTED", "CONFIRMED", "REJECTED", "REFUNDED")
PAYMENT_KINDS = ("SIGNUP", "VIP")  # VIP = 2주 이용권 (2026-10-03)


class Payment(Base):
    """가입비·VIP 입금 기록. 사용자는 입금자명에 실명 대신 결제 코드(code)를 적는다.

    관리자 화면에는 결제 코드·금액만 보여주고 닉네임·이메일은 보여주지 않는다 (익명성).
    """

    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(20), default="SIGNUP", nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    code: Mapped[str] = mapped_column(String(12), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="CREATED", nullable=False, index=True)
    created_at: Mapped[datetime] = created_at()
    requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("admin_users.id"), nullable=True
    )
