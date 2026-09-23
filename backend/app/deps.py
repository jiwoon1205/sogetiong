from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models.matching import AdminRole, AdminUser
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing token")

    token = credentials.credentials
    try:
        payload = decode_token(token)
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token") from exc

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token missing subject")

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found")
    if user.status != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="account is not active")

    return {"id": str(user.id), "role": payload.get("role", "USER"), "status": user.status}


def require_role(current_user: dict, allowed_roles: str | set[str]):
    user_role = str(current_user.get("role", "")).upper()
    if isinstance(allowed_roles, str):
        allowed = {allowed_roles.upper()}
    else:
        allowed = {role.upper() for role in allowed_roles}

    if user_role not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient role permissions")
    return current_user


def require_admin(current_user: dict):
    return require_role(current_user, {"SUPER_ADMIN", "PHOTO_REVIEWER", "MODERATOR"})


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing admin token")
    try:
        payload = decode_token(credentials.credentials)
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid admin token") from exc

    admin_id = payload.get("sub")
    admin = db.query(AdminUser).filter(AdminUser.id == admin_id, AdminUser.status == "ACTIVE").first()
    if admin is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin account is not active")
    role = db.query(AdminRole).filter(AdminRole.id == admin.role_id).first()
    if role is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin role is not configured")
    return {"id": str(admin.id), "role": role.name, "status": admin.status}
