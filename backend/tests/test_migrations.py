"""DB 구조 변경 파일(마이그레이션) 검사.

두 작업에서 각각 마이그레이션을 만들면 둘 다 같은 이전 버전을 가리켜 "갈림길"(head 2개)이 생긴다.
그러면 서버가 켜질 때 `alembic upgrade head`가 실패해서 backend가 계속 재시작된다 (2026-09-30 실제 발생).
배포 전에 테스트에서 먼저 잡는다.
"""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_migrations_have_a_single_head():
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    heads = ScriptDirectory.from_config(cfg).get_heads()
    assert len(heads) == 1, f"마이그레이션 끝이 {len(heads)}개입니다: {heads}. 새 파일의 down_revision을 최신 것으로 이어 주세요."
