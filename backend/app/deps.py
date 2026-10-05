"""로그인 확인·권한 확인 의존성.

모든 보호된 API는 여기의 함수를 거친다:
Authentication(누구인가) + Authorization(권한이 있는가). 자원 소유 확인은 각 API에서 한다.
"""

import uuid
from dataclasses import dataclass
from datetime import timedelta

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_token, tokens_match
from app.core.time import as_utc, utcnow
from app.db.session import get_db
from app.models.admin import ALL_PERMISSIONS, SUPER_ADMIN_ROLE, AdminSession, AdminUser
from app.models.user import User, UserSession
from app.services import push_service
from app.services.session_service import CSRF_HEADER, mark_user_active

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

# /docs 화면에 Authorize 버튼을 띄우기 위한 선언 (실제 토큰 읽기는 _read_token에서)
_bearer_docs = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    id: uuid.UUID
    user: User
    session: UserSession


@dataclass
class CurrentAdmin:
    id: uuid.UUID
    admin: AdminUser
    role: str
    permissions: set[str]
    session: AdminSession


LAST_ACTIVE_INTERVAL = timedelta(minutes=10)


def _unauthorized(detail: str = "로그인이 필요합니다.") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def _read_token(request: Request, cookie_name: str) -> tuple[str | None, bool]:
    """(토큰, 쿠키로 왔는지)"""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None, False
    return request.cookies.get(cookie_name), True


def _check_csrf(request: Request, from_cookie: bool, csrf_hash: str) -> None:
    """쿠키로 로그인한 경우, 데이터를 바꾸는 요청에는 CSRF 헤더가 필요하다."""
    if not from_cookie or request.method in SAFE_METHODS:
        return
    if not tokens_match(request.headers.get(CSRF_HEADER), csrf_hash):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF 토큰이 올바르지 않습니다.")


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    _docs: HTTPAuthorizationCredentials | None = Depends(_bearer_docs),
) -> CurrentUser:
    settings = get_settings()
    token, from_cookie = _read_token(request, settings.session_cookie_name)
    if not token:
        raise _unauthorized()

    session = db.query(UserSession).filter(UserSession.token_hash == hash_token(token)).first()
    now = utcnow()
    if session is None or as_utc(session.expires_at) <= now:
        raise _unauthorized("로그인이 만료되었습니다. 다시 로그인해주세요.")

    _check_csrf(request, from_cookie, session.csrf_hash)

    user = db.get(User, session.user_id)
    if user is None or user.status != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="이용할 수 없는 계정입니다.")

    changed = False
    # 사용할 때마다 만료 연장 (1시간에 한 번만 DB에 기록)
    if now - as_utc(session.last_used_at) > timedelta(hours=1):
        session.last_used_at = now
        session.expires_at = now + timedelta(days=settings.session_days)
        changed = True
    # 마지막 접속 시각 + 하루 접속 기록 (10분에 한 번만 DB에 기록)
    if user.last_active_at is None or now - as_utc(user.last_active_at) > LAST_ACTIVE_INTERVAL:
        mark_user_active(db, user, now)
        changed = True
    if changed:
        db.commit()
    # 지금 사이트를 쓰고 있다는 표시 (메모리에만). 이러면 방금 온 메시지를 휴대폰 알림으로 또 보내지 않는다.
    push_service.mark_seen(user.id)

    return CurrentUser(id=user.id, user=user, session=session)


def _load_admin(request: Request, db: Session, require_mfa: bool) -> CurrentAdmin:
    settings = get_settings()
    token, from_cookie = _read_token(request, settings.admin_session_cookie_name)
    if not token:
        raise _unauthorized("관리자 로그인이 필요합니다.")

    session = db.query(AdminSession).filter(AdminSession.token_hash == hash_token(token)).first()
    if session is None or as_utc(session.expires_at) <= utcnow():
        raise _unauthorized("관리자 로그인이 만료되었습니다.")
    if require_mfa and session.mfa_verified_at is None:
        raise _unauthorized("2단계 인증이 필요합니다.")

    _check_csrf(request, from_cookie, session.csrf_hash)

    admin = db.get(AdminUser, session.admin_id)
    if admin is None or admin.status != "ACTIVE" or admin.role is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="비활성화된 관리자 계정입니다.")

    permissions = set(admin.role.permissions_json or [])
    if admin.role.name == SUPER_ADMIN_ROLE:
        # 최고 관리자는 DB에 저장된 목록과 상관없이 모든 권한을 가진다
        permissions |= ALL_PERMISSIONS
    return CurrentAdmin(
        id=admin.id,
        admin=admin,
        role=admin.role.name,
        permissions=permissions,
        session=session,
    )


def get_admin_pending_mfa(request: Request, db: Session = Depends(get_db)) -> CurrentAdmin:
    """비밀번호만 확인된 상태 (2단계 인증 API 전용)."""
    return _load_admin(request, db, require_mfa=False)


def get_current_admin(request: Request, db: Session = Depends(get_db)) -> CurrentAdmin:
    return _load_admin(request, db, require_mfa=True)


def require_permission(permission: str):
    """사용 예: admin: CurrentAdmin = Depends(require_permission("photos:read"))"""

    def dependency(admin: CurrentAdmin = Depends(get_current_admin)) -> CurrentAdmin:
        if admin.role == SUPER_ADMIN_ROLE:
            return admin  # 최고 관리자는 항상 통과 (새 권한을 목록에 넣는 걸 잊어도 막히지 않게)
        if permission not in admin.permissions:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="권한이 없습니다.")
        return admin

    return dependency
