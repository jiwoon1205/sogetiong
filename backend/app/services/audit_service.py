from sqlalchemy.orm import Session

from app.models.matching import AuditLog


class AuditService:
    @staticmethod
    def record(
        db: Session,
        *,
        admin_id: str,
        action: str,
        target_type: str,
        target_id: str | None,
        metadata: dict | None = None,
    ) -> None:
        db.add(
            AuditLog(
                admin_id=admin_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                metadata_json=metadata,
            )
        )
