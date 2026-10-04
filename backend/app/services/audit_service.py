from fastapi import Request
from sqlalchemy.orm import Session

from app.core.rate_limit import client_ip
from app.models.admin import AuditLog


def record(
    db: Session,
    *,
    admin_id,
    action: str,
    target_type: str,
    target_id=None,
    request: Request | None = None,
    metadata: dict | None = None,
) -> None:
    """관리자 행위를 기록한다. metadata에는 개인정보 원문을 넣지 않는다 (설계도 §31).
    commit은 호출한 쪽에서 한다."""
    ua = request.headers.get("user-agent") if request else None
    db.add(
        AuditLog(
            admin_id=admin_id,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            ip_address=client_ip(request) if request else None,
            user_agent=ua[:300] if ua else None,
            metadata_json=metadata,
        )
    )
