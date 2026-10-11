"""슈퍼 라이크 (2026-10-12, `슈퍼 라이크 설계 (2026-10-12)`).

규칙
- 1개 SUPER_LIKE_PRICE(1,000원). 직접 입금으로 한 번에 1~SUPER_LIKE_MAX_QUANTITY(10)개를 산다. 기간 없음, 계정에 쌓인다.
  판매는 이용권과 같은 스위치(MEMBERSHIP_ENABLED)를 따른다. 체험 이용자도 살 수 있다 (볼 수 있는 승인 사진이 있어야 함).
- 추천에 뜬 사람(조건·차단·이미 LIKE/매칭 아님)에게 보내면 상대가 LIKE하지 않아도 바로 매칭된다.
  둘 중 한 명이 매칭 정지면 보통 매칭처럼 숨김 매칭이 된다 (본인은 모름).
- 안전장치: 받은 사람이 답장하기 전까지 보낸 사람은 메시지 1개만 보낼 수 있다 (message_locked).
  받은 사람은 언제든 대화 끝내기·차단·신고를 할 수 있다 (기존 기능).
- 받은 사람에게는 "슈퍼 라이크로 연결됐어요"가 보인다 (알림·대화 목록·대화방).
- 하루 LIKE 한도·무료 체험 LIKE 개수와 따로 센다 (likes.is_super).
- 환불: 산 개수를 하나도 안 썼을 때만 (남은 개수가 그 결제 개수 이상) → admin.refund_payment
- 관리자가 직접 줄 수 있다 (사유·감사 로그) → admin.give_user_super_likes
"""

import uuid

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.matching import Match, Message
from app.models.payment import Payment
from app.models.user import User
from app.services import payment_service

KIND = "SUPER_LIKE"


def price() -> int:
    return get_settings().super_like_price


def max_quantity() -> int:
    return get_settings().super_like_max_quantity


def clamp_quantity(quantity: int | None) -> int:
    return max(1, min(max_quantity(), int(quantity or 1)))


def get_or_create_payment(db: Session, user: User, quantity: int | None = None) -> Payment:
    """슈퍼 라이크 결제 코드. 아직 "입금 완료했어요"를 안 눌렀으면(CREATED) 개수·금액을 지금 고른 대로 맞춘다.
    누른 뒤(REQUESTED)에는 개수·금액이 바뀌지 않는다. commit은 호출한 쪽에서."""
    payment = payment_service.open_payment(db, user.id, KIND)
    if payment is None:
        q = clamp_quantity(quantity)
        payment = Payment(
            user_id=user.id, kind=KIND, quantity=q, amount=q * price(), code=payment_service._new_code(db), status="CREATED"
        )
        db.add(payment)
        db.flush()
    elif payment.status == "CREATED":
        q = clamp_quantity(quantity if quantity is not None else payment.quantity)
        payment.quantity = q
        payment.amount = q * price()
    return payment


def use_one(db: Session, user: User) -> bool:
    """슈퍼 라이크 1개 쓰기. 동시에 여러 번 눌러도 0 아래로 내려가지 않게 DB에서 조건부로 줄인다. 썼으면 True."""
    updated = (
        db.query(User)
        .filter(User.id == user.id, User.super_likes > 0)
        .update({User.super_likes: User.super_likes - 1}, synchronize_session=False)
    )
    db.refresh(user, ["super_likes"])
    return updated == 1


def add(user: User, count: int) -> None:
    user.super_likes = max(0, (user.super_likes or 0) + count)


def message_locked(db: Session, match: Match, user_id: uuid.UUID) -> bool:
    """슈퍼 라이크를 보낸 사람이, 상대가 답장하기 전에 이미 메시지 1개를 보냈으면 True (더 못 보냄)."""
    if match.super_like_by != user_id:
        return False
    partner = match.partner_of(user_id)
    replied = db.query(Message.id).filter(Message.match_id == match.id, Message.sender_user_id == partner).first()
    if replied is not None:
        return False
    sent = db.query(Message.id).filter(Message.match_id == match.id, Message.sender_user_id == user_id).first()
    return sent is not None


def view(user: User) -> dict:
    """/me·추천 화면용."""
    return {"count": user.super_likes or 0, "price": price(), "max_quantity": max_quantity()}
