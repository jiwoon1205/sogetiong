"""개발 환경 자동 준비.

APP_ENV=dev 로 서버를 켜면:
1) DB 테이블을 최신 구조로 맞추고 (alembic upgrade head)
2) 학교·캠퍼스·학과 같은 기본 데이터가 없으면 넣는다 (seed)

운영(prod) 환경에서는 아무것도 하지 않는다. 운영에서는 배포 과정에서 직접 실행한다.
"""

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.core.config import get_settings

logger = logging.getLogger("uvicorn.error")
BACKEND_DIR = Path(__file__).resolve().parents[2]


def prepare_dev_database() -> None:
    settings = get_settings()
    if settings.environment != "dev":
        return

    # 어느 폴더에서 서버를 켜도 동작하도록 절대 경로를 쓴다
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")

    from app.db.session import SessionLocal
    from app.models import University
    from app.scripts import seed

    db = SessionLocal()
    try:
        has_data = db.query(University.id).first() is not None
    finally:
        db.close()
    if not has_data:
        seed.run()
        logger.info("기본 데이터(학교·캠퍼스·학과·관심사)를 넣었습니다.")
    logger.info("개발용 DB 준비 완료")
