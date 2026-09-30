"""로그인 세션 발급·삭제와 쿠키 설정.

브라우저: HttpOnly 쿠키(session) + JS가 읽는 CSRF 쿠키(csrf_token)
앱(향후 모바일): 요청 헤더에 `X-Client-Type: app`을 넣으면 쿠키 대신
응답 body로 session_token을 받고, 이후 `Authorization: Bearer <토큰>`으로 보낸다.
"""

import uuid
from dataclasses import dataclass
from datetime import timedelta

from fastapi import Request, Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.rate_limit import client_ip
from app.core.security import hash_token, new_token
from app.core.time import utcnow
from app.models.admin import AdminSession
from app.models.user import User, UserSession

APP_CLIENT_HEADER = "X-Client-Type"
CSRF_HEADER = "X-CSRF-Token"


@dataclass
class IssuedSession:
    token: str
    csrf_token: str


def is_app_client(request: Request) -> bool:
    return request.headers.get(APP_CLIENT_HEADER, "").lower() == "app"


def _user_agent(request: Request) -> str | None:
    ua = request.headers.get("user-agent")
    return ua[:300] if ua else None


# ---------- 사용자 ----------

def create_user_session(db: Session, user_id: uuid.UUID, request: Request) -> IssuedSession:
    settings = get_settings()
    token, csrf = new_token(), new_token()
    now = utcnow()
    user = db.get(User, user_id)
    if user is not None:
        user.last_active_at = now  # 로그인·가입 = 접속
    db.add(
        UserSession(
            user_id=user_id,
            token_hash=hash_token(token),
            csrf_hash=hash_token(csrf),
            expires_at=now + timedelta(days=settings.session_days),
            last_used_at=now,
            ip_address=client_ip(request),
            user_agent=_user_agent(request),
        )
    )
    return IssuedSession(token=token, csrf_token=csrf)


def revoke_all_user_sessions(db: Session, user_id: uuid.UUID) -> None:
    db.query(UserSession).filter(UserSession.user_id == user_id).delete(synchronize_session=False)


def set_user_cookies(response: Response, issued: IssuedSession) -> None:
    settings = get_settings()
    max_age = settings.session_days * 24 * 3600
    _set_pair(response, settings.session_cookie_name, settings.csrf_cookie_name, issued, max_age)


def clear_user_cookies(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.delete_cookie(settings.csrf_cookie_name, path="/")


def auth_response_body(request: Request, issued: IssuedSession, extra: dict | None = None) -> dict:
    body = dict(extra or {})
    body["csrf_token"] = issued.csrf_token
    if is_app_client(request):
        body["session_token"] = issued.token
    return body


# ---------- 관리자 ----------

def create_admin_session(db: Session, admin_id: uuid.UUID, request: Request) -> IssuedSession:
    settings = get_settings()
    token, csrf = new_token(), new_token()
    db.add(
        AdminSession(
            admin_id=admin_id,
            token_hash=hash_token(token),
            csrf_hash=hash_token(csrf),
            expires_at=utcnow() + timedelta(hours=settings.admin_session_hours),
            ip_address=client_ip(request),
            user_agent=_user_agent(request),
        )
    )
    return IssuedSession(token=token, csrf_token=csrf)


def set_admin_cookies(response: Response, issued: IssuedSession) -> None:
    settings = get_settings()
    max_age = settings.admin_session_hours * 3600
    _set_pair(response, settings.admin_session_cookie_name, settings.admin_csrf_cookie_name, issued, max_age)


def clear_admin_cookies(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(settings.admin_session_cookie_name, path="/")
    response.delete_cookie(settings.admin_csrf_cookie_name, path="/")


def _set_pair(response: Response, session_name: str, csrf_name: str, issued: IssuedSession, max_age: int) -> None:
    secure = get_settings().cookies_secure
    response.set_cookie(
        session_name, issued.token, max_age=max_age, httponly=True, secure=secure, samesite="lax", path="/"
    )
    # CSRF 쿠키는 프론트엔드 JS가 읽어서 X-CSRF-Token 헤더에 넣어야 하므로 HttpOnly가 아니다.
    response.set_cookie(
        csrf_name, issued.csrf_token, max_age=max_age, httponly=False, secure=secure, samesite="lax", path="/"
    )
