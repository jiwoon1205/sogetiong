"""학교 이메일 인증 로직 (설계도 §2.1, §40)."""

import uuid
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_token, new_token, new_verification_code, tokens_match
from app.core.time import as_utc, utcnow
from app.models.matching import Block
from app.models.photo import AppearanceEvaluation, UserPhoto
from app.models.university import University
from app.models.user import User, VerificationToken

MAX_CODE_ATTEMPTS = 5
PURPOSE_SIGNUP = "SIGNUP"
PURPOSE_PASSWORD_RESET = "PASSWORD_RESET"


def normalize_email(email: str) -> str:
    return email.strip().lower()


# ---------- 탈퇴·재가입 ----------

def email_fingerprint(email: str) -> str:
    """이메일 지문. 원래 주소로 되돌릴 수 없고, 같은 주소면 항상 같은 값이 나온다.

    주의: SECRET_KEY로 만들기 때문에 SECRET_KEY를 바꾸면 예전 계정을 알아볼 수 없게 된다.
    """
    return hash_token(f"email:{normalize_email(email)}")


def anonymized_email(user_id: uuid.UUID) -> str:
    """탈퇴한 계정에 넣는 가짜 주소. 원래 주소가 비워져야 같은 메일로 다시 가입할 수 있다."""
    return f"deleted-{user_id}@deleted.invalid"


def previous_accounts(db: Session, email: str) -> list[User]:
    """같은 이메일로 예전에 가입했던 계정들 (탈퇴·정지 포함)."""
    return db.query(User).filter(User.email_hash == email_fingerprint(email)).all()


def rejoin_block_reason(db: Session, email: str) -> str | None:
    """다시 가입할 수 없으면 그 이유(사용자에게 보여줄 문장), 가능하면 None.

    이메일 인증을 통과한 본인에게만 보여주므로 이유를 알려줘도 된다.
    """
    previous = previous_accounts(db, email)
    if any(u.status == "BANNED" for u in previous):
        return "이용이 영구 제한된 계정이라 다시 가입할 수 없습니다."

    days = get_settings().rejoin_cooldown_days
    deleted_times = [as_utc(u.deleted_at) for u in previous if u.deleted_at is not None]
    if days > 0 and deleted_times:
        available_at = max(deleted_times) + timedelta(days=days)
        if utcnow() < available_at:
            kst = available_at + timedelta(hours=9)
            return f"탈퇴 후 {days}일이 지나야 다시 가입할 수 있습니다. ({kst:%Y년 %m월 %d일 %H:%M} 이후 가능)"
    return None


def carry_over_blocks(db: Session, previous_ids: list[uuid.UUID], new_user_id: uuid.UUID) -> None:
    """예전 계정의 차단 관계를 새 계정으로 옮긴다.

    이걸 하지 않으면, 나를 차단한 사람에게 탈퇴 후 재가입만으로 다시 추천될 수 있다.
    (반대로 내가 예전에 차단했던 사람도 계속 차단 상태로 둔다.)
    """
    if not previous_ids:
        return
    pairs: set[tuple[uuid.UUID, uuid.UUID]] = set()
    for blocker, _ in db.query(Block.blocker_user_id, Block.blocked_user_id).filter(Block.blocked_user_id.in_(previous_ids)):
        if blocker not in previous_ids:
            pairs.add((blocker, new_user_id))
    for _, blocked in db.query(Block.blocker_user_id, Block.blocked_user_id).filter(Block.blocker_user_id.in_(previous_ids)):
        if blocked not in previous_ids:
            pairs.add((new_user_id, blocked))
    db.add_all([Block(blocker_user_id=a, blocked_user_id=b) for a, b in pairs])


def carry_over_account(db: Session, previous: list[User], new_user: User) -> None:
    """탈퇴 후 다시 가입한 사람에게 예전 계정의 것을 이어준다 (2026-10-05).

    탈퇴 → 재가입으로 외모 점수·재검토 대기·이용권·매칭 정지를 "초기화"하지 못하게 한다.
    - 사진·외모 평가(점수·등급) 기록을 새 계정으로 옮긴다 → 사진 단계 없이 바로 이어서 이용,
      재검토 대기(마지막 평가 후 7일/VIP 3일)와 "바로 재검토 평생 1번" 사용 여부도 그대로 이어진다.
      (탈퇴 7일 뒤 사진 파일은 지워지지만, 평가 기록은 남아서 그대로 옮겨진다)
    - 남은 이용권·VIP 기간, 쌓아 둔 이용권 일수를 이어준다 (탈퇴해 있던 동안에도 기간은 흘러간다).
      옮긴 뒤 예전 계정의 값은 비운다 (여러 번 탈퇴·재가입해도 두 번 받지 않게).
    - 매칭 정지 상태도 이어진다 (본인은 모름).
    차단 관계는 carry_over_blocks가 따로 옮긴다.
    """
    old = [u for u in previous if u.status == "DELETED" and u.id != new_user.id]
    if not old:
        return
    ids = [u.id for u in old]
    db.query(UserPhoto).filter(UserPhoto.user_id.in_(ids)).update({"user_id": new_user.id}, synchronize_session=False)
    db.query(AppearanceEvaluation).filter(AppearanceEvaluation.user_id.in_(ids)).update(
        {"user_id": new_user.id}, synchronize_session=False
    )

    def latest(values):
        values = [as_utc(v) for v in values if v is not None]
        return max(values) if values else None

    new_user.member_until = latest(u.member_until for u in old)
    new_user.vip_until = latest(u.vip_until for u in old)
    new_user.member_days_banked = sum(u.member_days_banked or 0 for u in old)
    new_user.signup_paid_at = latest(u.signup_paid_at for u in old)
    # 무료 체험 LIKE 사용 개수와 "사진 바로 재검토 1회" 구매 혜택도 이어진다 (2026-10-06).
    # 체험 개수는 예전 계정에서 비우지 않는다 (줄어드는 값이 아니라서 여러 번 재가입해도 늘지 않음)
    new_user.trial_likes_used = max([new_user.trial_likes_used or 0] + [u.trial_likes_used or 0 for u in old])
    new_user.rereview_granted_at = latest([new_user.rereview_granted_at] + [u.rereview_granted_at for u in old])
    if any(u.match_suspended for u in old):
        new_user.match_suspended = True
        new_user.match_suspended_at = latest(u.match_suspended_at for u in old)
    for u in old:
        u.member_until = None
        u.vip_until = None
        u.member_days_banked = 0


# ---------- 학교 이메일 인증 ----------

def find_university_for_email(db: Session, email: str) -> University | None:
    """이메일 도메인이 등록된(활성) 학교와 정확히 일치해야 한다."""
    domain = normalize_email(email).rsplit("@", 1)[-1]
    return db.query(University).filter(University.email_domain == domain, University.active.is_(True)).first()


def issue_verification_code(db: Session, email: str, purpose: str = PURPOSE_SIGNUP) -> str:
    settings = get_settings()
    code = new_verification_code()
    db.add(
        VerificationToken(
            email=normalize_email(email),
            purpose=purpose,
            code_hash=hash_token(code),
            expires_at=utcnow() + timedelta(minutes=settings.verification_code_minutes),
        )
    )
    db.commit()
    return code


def _check_latest_code(db: Session, email: str, code: str, purpose: str) -> VerificationToken | None:
    """이 이메일·용도로 가장 최근에 보낸 코드와 비교한다.

    새 코드를 받으면 이전 코드는 자동으로 못 쓰게 된다 (항상 최신 것만 확인).
    틀리면 시도 횟수를 늘리고, 5번 틀린 코드는 맞아도 거부한다.
    """
    token = (
        db.query(VerificationToken)
        .filter(VerificationToken.email == normalize_email(email), VerificationToken.purpose == purpose)
        .order_by(VerificationToken.created_at.desc())
        .first()
    )
    if token is None or token.verified_at is not None or as_utc(token.expires_at) <= utcnow():
        return None
    if token.attempt_count >= MAX_CODE_ATTEMPTS:
        return None
    if not tokens_match(code.strip(), token.code_hash):
        token.attempt_count += 1
        db.commit()
        return None
    return token


def verify_code_and_issue_ticket(db: Session, email: str, code: str) -> str | None:
    """인증번호가 맞으면 가입용 1회 티켓(원문)을 돌려준다. 틀리면 None."""
    settings = get_settings()
    token = _check_latest_code(db, email, code, PURPOSE_SIGNUP)
    if token is None:
        return None

    now = utcnow()
    ticket = new_token()
    token.verified_at = now
    token.ticket_hash = hash_token(ticket)
    token.ticket_expires_at = now + timedelta(minutes=settings.verification_ticket_minutes)
    db.commit()
    return ticket


def use_password_reset_code(db: Session, email: str, code: str) -> bool:
    """재설정 코드가 맞으면 '사용됨'으로 표시하고 True. (commit은 호출한 쪽에서)"""
    token = _check_latest_code(db, email, code, PURPOSE_PASSWORD_RESET)
    if token is None:
        return False
    now = utcnow()
    token.verified_at = now
    token.consumed_at = now
    return True


def find_valid_ticket(db: Session, ticket: str) -> VerificationToken | None:
    token = (
        db.query(VerificationToken)
        .filter(VerificationToken.ticket_hash == hash_token(ticket), VerificationToken.purpose == PURPOSE_SIGNUP)
        .first()
    )
    if token is None or token.consumed_at is not None:
        return None
    if token.ticket_expires_at is None or as_utc(token.ticket_expires_at) <= utcnow():
        return None
    return token
