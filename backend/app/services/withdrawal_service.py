"""탈퇴한 사람의 정보 정리 (2026-10-01).

규칙
- 탈퇴하면: 로그인 끊기, 진행 중인 대화 종료, 이메일 익명화, 상태 DELETED → 다른 사용자에게는 바로 안 보인다.
- 프로필·사진·관심사·매칭 조건은 관리자 확인용으로 7일(WITHDRAWN_RETENTION_DAYS) 동안 보관한다.
- 7일이 지나면 purge_expired()가 지운다. 백엔드가 켜져 있는 동안 1시간마다 자동으로 돈다 (app.main).
- 닉네임·성별은 탈퇴할 때 users.deleted_*에 따로 남겨서, 지운 뒤에도 관리자가 찾을 수 있다.
"""

import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.time import as_utc, utcnow
from app.services.storage_service import get_storage
from app.models.matching import ExcludedDepartment, MatchingPreference, PreferredCampus, PreferredDepartment
from app.models.photo import UserPhoto
from app.models.profile import PublicProfile, UserInterest
from app.models.user import User

logger = logging.getLogger(__name__)


def purge_at(deleted_at: datetime | None) -> datetime | None:
    """이 탈퇴자의 정보가 지워지는(지워진) 시각."""
    if deleted_at is None:
        return None
    return as_utc(deleted_at) + timedelta(days=get_settings().withdrawn_retention_days)


def purge_user_data(db: Session, user_id: uuid.UUID) -> None:
    """한 사람의 프로필·사진·관심사·매칭 조건을 지운다. 여러 번 불러도 괜찮다. commit은 부르는 쪽에서."""
    storage = get_storage()
    for photo in db.query(UserPhoto).filter(UserPhoto.user_id == user_id):
        if photo.storage_key:
            try:
                storage.delete(photo.storage_key)
            except FileNotFoundError:
                pass
        photo.storage_key = ""
        photo.upload_status = "DELETED"
    for model in (UserInterest, PreferredCampus, ExcludedDepartment, PreferredDepartment, MatchingPreference, PublicProfile):
        db.query(model).filter(model.user_id == user_id).delete(synchronize_session=False)


def purge_expired(db: Session, now: datetime | None = None) -> int:
    """보관 기간이 지난 탈퇴자의 정보를 지운다. 지운 사람 수를 돌려준다."""
    cutoff = (now or utcnow()) - timedelta(days=get_settings().withdrawn_retention_days)
    # 아직 지울 것이 남아 있는 사람만 (프로필이 있거나, 파일이 남은 사진이 있음)
    with_profile = db.query(PublicProfile.user_id)
    with_files = db.query(UserPhoto.user_id).filter(UserPhoto.storage_key != "")
    ids = [
        uid
        for (uid,) in db.query(User.id).filter(
            User.deleted_at.isnot(None),
            User.deleted_at <= cutoff,
            User.id.in_(with_profile) | User.id.in_(with_files),
        )
    ]
    for uid in ids:
        purge_user_data(db, uid)
    db.commit()
    if ids:
        logger.info("purged withdrawn users: %d", len(ids))
    return len(ids)
