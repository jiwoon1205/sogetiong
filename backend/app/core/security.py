"""비밀번호·토큰·인증번호를 안전하게 다루는 함수 모음."""

import hashlib
import hmac
import secrets
import uuid

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import get_settings

_hasher = PasswordHasher()  # Argon2id (설계도 §40)
_DUMMY_HASH = _hasher.hash("dummy-password-for-timing")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """틀린 이메일이어도 같은 시간이 걸리도록 dummy 해시와 비교한다."""
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def new_token() -> str:
    """세션 ID, CSRF 토큰, 인증 티켓에 쓰는 추측 불가능한 무작위 문자열."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """DB에는 토큰 원문 대신 이 값만 저장한다."""
    key = get_settings().secret_key.encode()
    return hmac.new(key, token.encode(), hashlib.sha256).hexdigest()


def tokens_match(token: str | None, token_hash: str | None) -> bool:
    if not token or not token_hash:
        return False
    return hmac.compare_digest(hash_token(token), token_hash)


def new_verification_code() -> str:
    """6자리 숫자 인증번호 (secrets 사용)."""
    return f"{secrets.randbelow(1_000_000):06d}"


def pseudonymous_code(user_id: uuid.UUID) -> str:
    """관리자 사진 검수 화면에 실제 ID 대신 보여줄 짧은 코드 (예: A38192)."""
    digest = hash_token(f"subject:{user_id}")
    return "U" + digest[:6].upper()
