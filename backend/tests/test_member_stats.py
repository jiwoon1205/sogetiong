"""머리말의 가입자 수·성비 (2026-10-05).

- 전체 가입자 수는 정지·탈퇴한 계정도 센다.
- 성비는 탈퇴하지 않은 전체 가입자로 계산한다 (2026-10-25 변경, 예전: 활성 사용자).
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
    assert r.json() == {"total": 0, "male_per_female": None, "female_pct": None, "multi_school": False}


def test_member_stats_ratio_uses_all_members_except_withdrawn(sent_codes, db):
    """2026-10-25: 성비는 탈퇴하지 않은 전체 가입자 기준 (사진 검수·접속·정지와 상관없이)."""
    admin = admin_login(db)
    ready_user(sent_codes, db, admin, "m@hufs.ac.kr", gender="MALE")
    ready_user(sent_codes, db, admin, "f1@hufs.ac.kr", gender="FEMALE")
    ready_user(sent_codes, db, admin, "old@hufs.ac.kr", gender="FEMALE")  # 10일 전 접속 → 그래도 셈
    ready_user(sent_codes, db, admin, "ban@hufs.ac.kr", gender="MALE")  # 정지 → 그래도 셈
    signup(sent_codes, db, "nophoto@hufs.ac.kr", gender="FEMALE")  # 사진 검수 전 → 그래도 셈
    gone = ready_user(sent_codes, db, admin, "gone@hufs.ac.kr", gender="MALE")  # 탈퇴 → 성비에서 빠짐, 총원엔 포함

    db.expire_all()
    old = db.query(User).filter(User.email == "old@hufs.ac.kr").one()
    db.query(UserDailyVisit).filter(UserDailyVisit.user_id == old.id).delete()
    db.add(UserDailyVisit(user_id=old.id, visit_date=kst_today() - timedelta(days=10)))
    db.query(User).filter(User.email == "ban@hufs.ac.kr").one().status = "SUSPENDED"
    db.commit()
    assert gone.delete("/api/v1/me", json={"password": "goodpass123"}).status_code == 200

    body = TestClient(app).get("/api/v1/stats/members").json()
    assert body["total"] == 6
    # 남 2(m, ban), 여 3(f1, old, nophoto) → 여 1 : 남 0.7, 막대는 여 60%
    assert body["male_per_female"] == 0.7
    assert body["female_pct"] == 60
