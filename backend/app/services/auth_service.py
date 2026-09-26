"""학교 이메일 인증 로직 (설계도 §2.1, §40)."""

from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_token, new_token, new_verification_code, tokens_match
from app.core.time import as_utc, utcnow
from app.models.university import University
from app.models.user import VerificationToken

MAX_CODE_ATTEMPTS = 5
PURPOSE_SIGNUP = "SIGNUP"
PURPOSE_PASSWORD_RESET = "PASSWORD_RESET"


def normalize_email(email: str) -> str:
    return email.strip().lower()


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
