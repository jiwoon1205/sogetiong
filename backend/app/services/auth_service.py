from datetime import datetime, timedelta

from app.core.security import hash_password, verify_password


class AuthService:
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
