"""학교 이메일 인증 로직 (설계도 §2.1, §40)."""

from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_token, new_token, new_verification_code, tokens_match
from app.core.time import as_utc, utcnow
from app.models.university import University
from app.models.user import VerificationToken

MAX_CODE_ATTEMPTS = 5


def normalize_email(email: str) -> str:
    return email.strip().lower()


def find_university_for_email(db: Session, email: str) -> University | None:
    """이메일 도메인이 등록된(활성) 학교와 정확히 일치해야 한다."""
    domain = normalize_email(email).rsplit("@", 1)[-1]
    return db.query(University).filter(University.email_domain == domain, University.active.is_(True)).first()


def issue_verification_code(db: Session, email: str) -> str:
    settings = get_settings()
    code = new_verification_code()
    db.add(
        VerificationToken(
            email=normalize_email(email),
            code_hash=hash_token(code),
            expires_at=utcnow() + timedelta(minutes=settings.verification_code_minutes),
        )
    )
    db.commit()
    return code


def verify_code_and_issue_ticket(db: Session, email: str, code: str) -> str | None:
    """인증번호가 맞으면 가입용 1회 티켓(원문)을 돌려준다. 틀리면 None."""
    settings = get_settings()
    token = (
        db.query(VerificationToken)
        .filter(VerificationToken.email == normalize_email(email))
        .order_by(VerificationToken.created_at.desc())
        .first()
    )
    now = utcnow()
    if token is None or token.verified_at is not None or as_utc(token.expires_at) <= now:
        return None
    if token.attempt_count >= MAX_CODE_ATTEMPTS:
        return None
    if not tokens_match(code.strip(), token.code_hash):
        token.attempt_count += 1
        db.commit()
        return None

    ticket = new_token()
    token.verified_at = now
    token.ticket_hash = hash_token(ticket)
    token.ticket_expires_at = now + timedelta(minutes=settings.verification_ticket_minutes)
    db.commit()
    return ticket


def find_valid_ticket(db: Session, ticket: str) -> VerificationToken | None:
    token = db.query(VerificationToken).filter(VerificationToken.ticket_hash == hash_token(ticket)).first()
    if token is None or token.consumed_at is not None:
        return None
    if token.ticket_expires_at is None or as_utc(token.ticket_expires_at) <= utcnow():
        return None
    return token
