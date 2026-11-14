"""좋아요 기록 표 like_events (2026-11-14) + export_stats.py의 날짜별 남녀 좋아요 칸.

- 좋아요를 보낼 때마다 like_events에 한 줄 (같은 사람에게 다시 보내도 지우지 않고 쌓인다)
- PASS는 기록하지 않는다
- export_stats.py: stats_daily.csv에 likes_FEMALE/MALE(정확), likes_est_*(어림값), likes_exact
"""

import csv
import subprocess
import sys
from pathlib import Path

from app.api.v1.matching import _upsert_action
from app.core.config import get_settings
from app.core.time import KST, utcnow
from app.models.matching import LikeEvent
from tests.conftest import admin_login, ready_user
from tests.test_membership import user_of


def test_each_like_is_recorded(sent_codes, db):
    admin = admin_login(db)
    him = ready_user(sent_codes, db, admin, "him@hufs.ac.kr", gender="MALE")
    her = ready_user(sent_codes, db, admin, "her@hufs.ac.kr", gender="FEMALE")
    other = ready_user(sent_codes, db, admin, "other@hufs.ac.kr", gender="MALE")
    assert him.post("/api/v1/likes", json={"profile_id": her.profile_id}).status_code == 200
    # 같은 사람에게 다시 좋아요 (3일 뒤 다시 보낸 경우와 같은 기록 경로)
    _upsert_action(db, user_of(db, him).id, user_of(db, her).id, "LIKE")
    db.commit()
    # PASS는 기록하지 않는다
    assert other.post("/api/v1/passes", json={"profile_id": her.profile_id}).status_code in (200, 204)

    rows = db.query(LikeEvent).filter(LikeEvent.from_user_id == user_of(db, him).id).order_by(LikeEvent.like_no).all()
    assert [r.like_no for r in rows] == [1, 2]
    assert db.query(LikeEvent).filter(LikeEvent.from_user_id == user_of(db, other).id).count() == 0


def test_export_daily_like_columns(sent_codes, db, tmp_path):
    admin = admin_login(db)
    him = ready_user(sent_codes, db, admin, "him@hufs.ac.kr", gender="MALE")
    her = ready_user(sent_codes, db, admin, "her@hufs.ac.kr", gender="FEMALE")
    assert him.post("/api/v1/likes", json={"profile_id": her.profile_id}).status_code == 200
    _upsert_action(db, user_of(db, him).id, user_of(db, her).id, "LIKE")
    db.commit()
    assert her.post("/api/v1/likes", json={"profile_id": him.profile_id}).status_code == 200

    db_path = get_settings().database_url.replace("sqlite:///", "")
    script = Path(__file__).resolve().parents[2] / "deploy" / "export_stats.py"
    subprocess.run([sys.executable, str(script), db_path, str(tmp_path)], check=True, capture_output=True)
    with open(tmp_path / "stats_daily.csv", encoding="utf-8-sig") as f:
        rows = {r["date"]: r for r in csv.DictReader(f)}
    today = rows[utcnow().astimezone(KST).date().isoformat()]
    assert today["likes_MALE"] == "2" and today["likes_FEMALE"] == "1"  # 정확한 값: 같은 사람에게 2번도 2
    assert today["likes_est_MALE"] == "1"  # 어림값: 두 사람 사이 마지막 좋아요만 남아 1
    assert today["likes_exact"] == "0"  # 기록을 시작한 날은 하루 중간부터라 믿지 않는다
