from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

settings = get_settings()
_is_sqlite = settings.database_url.startswith("sqlite")

engine = create_engine(
    settings.database_url,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    # 연결 수를 FastAPI 작업 스레드 수(40)보다 넉넉하게 둔다.
    # 기본값(5+10=15)이면 요청이 몰릴 때 스레드들이 DB 연결을 기다리며 서로 막혀
    # 서버 전체가 30초씩 멈춘다 (부하 테스트 200명에서 확인, 2026-09-30).
    pool_size=10,
    max_overflow=40,
    pool_timeout=10,
)

if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _configure_sqlite(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        # WAL: 읽는 중에도 쓸 수 있어 동시 접속에 강하다. busy_timeout: 잠깐 잠겨 있으면 5초까지 기다린다.
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
