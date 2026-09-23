from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.matching import VerificationToken


class AuthService:
    ALLOWED_SCHOOL_DOMAINS = {"hufs.ac.kr"}

    @staticmethod
    def is_valid_school_email(email: str) -> bool:
        normalized = email.strip().lower()
        return normalized.endswith("@hufs.ac.kr") and "@" in normalized

    @staticmethod
    def register_user(email: str, password: str) -> dict:
        return {
            "email": email,
            "password_hash": hash_password(password),
            "status": "PENDING",
        }

    @staticmethod
    def authenticate_user(stored_hash: str, password: str) -> bool:
        return verify_password(password, stored_hash)

    @staticmethod
    def create_verification_code() -> str:
        import random
        import string

        alphabet = string.ascii_uppercase + string.digits
        return "".join(random.choice(alphabet) for _ in range(8))

    @staticmethod
    def create_verification_token() -> dict:
        return {
            "code": AuthService.create_verification_code(),
            "expires_at": datetime.utcnow() + timedelta(minutes=10),
        }

    @staticmethod
    def store_verification_code(db: Session, email: str, code: str) -> VerificationToken:
        token = VerificationToken(
            email=email.lower().strip(),
            code_hash=hash_password(code),
            expires_at=datetime.utcnow() + timedelta(minutes=10),
        )
        db.add(token)
        db.commit()
        db.refresh(token)
        return token

    @staticmethod
    def verify_verification_code(db: Session, email: str, code: str) -> bool:
        normalized_email = email.lower().strip()
        token = (
            db.query(VerificationToken)
            .filter(VerificationToken.email == normalized_email)
            .order_by(VerificationToken.created_at.desc())
            .first()
        )
        if token is None:
            return False
        if token.used_at is not None or token.expires_at < datetime.utcnow():
            return False
        if token.attempt_count >= 5:
            return False
        if not verify_password(code, token.code_hash):
            token.attempt_count += 1
            db.commit()
            return False

        token.used_at = datetime.utcnow()
        db.commit()
        return True
