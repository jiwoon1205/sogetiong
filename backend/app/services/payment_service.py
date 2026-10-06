"""이용권·VIP 직접 입금 (2026-10-03, 2026-10-04 구독제).

흐름: 결제 코드 받기(CREATED) → "입금했어요"(REQUESTED)
     → 관리자가 통장 확인 → CONFIRMED(이용권 기간 추가, membership_service) 또는 REJECTED(다시 요청 가능)
kind: SIGNUP = 기본 이용권 (이름은 예전 그대로 둔다), VIP = VIP (기본 포함). 기간: 정식 2주 / 베타 기간에 산 것 4주 (2026-10-06)
환불(REFUNDED)은 기본 이용권이 아직 시작되지 않았고 사진 검수도 받지 않았을 때만 된다.
누가 언제 내야 하는지는 membership_service에 있다.
"""

import secrets
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.time import KST, utcnow
from app.models.payment import Payment
from app.models.photo import UserPhoto
from app.models.user import User

# 헷갈리는 글자(0·O·1·I·L)를 뺀 영문 대문자 + 숫자. 은행 입금자명 칸에 그대로 적는다.
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 6
# 아직 처리가 끝나지 않은 결제 (사용자 한 명에 하나만 있다)
OPEN_STATUSES = ("CREATED", "REQUESTED", "REJECTED")


def is_payment_open(now: datetime | None = None) -> bool:
    """지금(한국 시간)이 결제 가능 시간인가. 기본 오전 6시 ~ 밤 12시."""
    settings = get_settings()
    hour = (now or utcnow()).astimezone(KST).hour
    return settings.payment_open_hour <= hour < settings.payment_close_hour


def _new_code(db: Session) -> str:
    while True:
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        if db.query(Payment.id).filter(Payment.code == code).first() is None:
            return code


def open_payment(db: Session, user_id: uuid.UUID, kind: str = "SIGNUP") -> Payment | None:
    return (
        db.query(Payment)
        .filter(Payment.user_id == user_id, Payment.kind == kind, Payment.status.in_(OPEN_STATUSES))
        .order_by(Payment.created_at.desc())
        .first()
    )


def get_or_create_payment(db: Session, user: User, kind: str = "SIGNUP", amount: int | None = None) -> Payment:
    """처리 중인 결제가 있으면 그것을, 없으면 새 결제 코드를 만든다 (commit은 호출한 쪽에서).

    같은 사람은 다시 들어와도 같은 코드를 본다. 확인·환불이 끝나면 다음에는 새 코드가 생긴다.
    amount: 지금 가격. 아직 "입금했어요"를 안 누른 결제(CREATED)는 지금 가격으로 맞춘다
    → 가격을 바꾼 뒤 예전 가격 코드로 입금하는 일이 없다. 누른 뒤에는 가격이 바뀌지 않는다.
    """
    if amount is None:
        from app.services import membership_service  # 할인가 계산 (2026-10-06)

        amount = membership_service.price()
    payment = open_payment(db, user.id, kind)
    if payment is None:
        payment = Payment(user_id=user.id, kind=kind, amount=amount, code=_new_code(db), status="CREATED")
        db.add(payment)
        db.flush()
    elif payment.status == "CREATED" and payment.amount != amount:
        payment.amount = amount
    return payment


def has_been_reviewed(db: Session, user_id: uuid.UUID) -> bool:
    """사진 검수를 한 번이라도 받았나 (승인·반려 상관없이). 받았으면 환불할 수 없다."""
    return (
        db.query(UserPhoto.id).filter(UserPhoto.user_id == user_id, UserPhoto.reviewed_at.isnot(None)).first()
        is not None
    )


def latest_status_by_user(db: Session, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    """사람별 가장 최근 기본 이용권 결제 상태 (관리자 사용자 목록의 가입 단계용)."""
    if not user_ids:
        return {}
    rows = (
        db.query(Payment.user_id, Payment.status, Payment.created_at)
        .filter(Payment.user_id.in_(user_ids), Payment.kind == "SIGNUP")
        .order_by(Payment.created_at)
        .all()
    )
    return {uid: st for uid, st, _ in rows}  # 나중 것이 앞의 것을 덮는다 = 가장 최근
