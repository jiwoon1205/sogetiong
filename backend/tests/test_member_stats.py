"""머리말의 가입자 수·성비 (2026-10-05).

- 전체 가입자 수는 정지·탈퇴한 계정도 센다.
- 성비는 활성 사용자(사진 검수 완료 + 최근 7일 접속)만으로 계산한다.
- 로그인 없이 볼 수 있다.
"""

from datetime import timedelta

from fastapi.testclient import TestClient

from app.core.time import kst_today
from app.main import app
from app.models.user import User, UserDailyVisit

from tests.conftest import admin_login, ready_user, signup


def test_member_stats_without_login_when_empty():
    r = TestClient(app).get("/api/v1/stats/members")
    assert r.status_code == 200
    assert r.json() == {"total": 0, "male_per_female": None, "female_pct": None}


def test_member_stats_total_includes_all_and_ratio_uses_active_only(sent_codes, db):
    admin = admin_login(db)
    ready_user(sent_codes, db, admin, "m@hufs.ac.kr", gender="MALE")
    ready_user(sent_codes, db, admin, "f1@hufs.ac.kr", gender="FEMALE")
    ready_user(sent_codes, db, admin, "f2@hufs.ac.kr", gender="FEMALE")
    ready_user(sent_codes, db, admin, "old@hufs.ac.kr", gender="FEMALE")  # 10일 전 접속 → 성비에서 빠짐
    ready_user(sent_codes, db, admin, "ban@hufs.ac.kr", gender="MALE")  # 정지 → 성비에서 빠짐, 총원엔 포함
    signup(sent_codes, db, "nophoto@hufs.ac.kr", gender="MALE")  # 사진 검수 전 → 성비에서 빠짐

    db.expire_all()
    old = db.query(User).filter(User.email == "old@hufs.ac.kr").one()
    db.query(UserDailyVisit).filter(UserDailyVisit.user_id == old.id).delete()
    db.add(UserDailyVisit(user_id=old.id, visit_date=kst_today() - timedelta(days=10)))
    db.query(User).filter(User.email == "ban@hufs.ac.kr").one().status = "SUSPENDED"
    db.commit()

    body = TestClient(app).get("/api/v1/stats/members").json()
    assert body["total"] == 6
    # 활성: 남 1(m), 여 2(f1, f2) → 여 1 : 남 0.5, 막대는 여 67%
    assert body["male_per_female"] == 0.5
    assert body["female_pct"] == 67
