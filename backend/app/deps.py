from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db

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

    user = {"id": user_id, "role": payload.get("role", "USER")}
    return user


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
