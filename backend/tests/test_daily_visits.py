"""하루 접속 기록 · 활성 사용자 · 성별 구분 · 활동 점수 (2026-10-01).

- 하루(한국 시간)에 한 줄만 쌓인다.
- 관리자 대시보드의 "활성 사용자" = 최근 7일 안에 접속한 정상 계정 (전체 가입자와 다르게 나와야 한다).
- 관리자 사용자 목록에 성별이 보이고, 남자/여자로 걸러볼 수 있다.
- 추천에서 점수가 같으면 자주 접속한 사람이 먼저 나온다.
"""

from datetime import timedelta

from app.core.time import kst_today, utcnow
from app.models.user import User, UserDailyVisit

from tests.conftest import admin_login, discover_ids, ready_user, signup


def _user(db, email):
    db.expire_all()
    return db.query(User).filter(User.email == email).one()


def _visits(db, user_id):
    db.expire_all()
    return db.query(UserDailyVisit).filter(UserDailyVisit.user_id == user_id).all()


def test_one_row_per_day(sent_codes, db):
    client = signup(sent_codes, db, "a@hufs.ac.kr")
    user = _user(db, "a@hufs.ac.kr")
    assert [v.visit_date for v in _visits(db, user.id)] == [kst_today()]  # 가입 = 오늘 접속

    # 같은 날 여러 번 써도 한 줄
    user.last_active_at = utcnow() - timedelta(minutes=11)
    db.commit()
    client.get("/api/v1/me/profile")
    assert len(_visits(db, user.id)) == 1

    # 어제 마지막으로 접속했던 사람이 오늘 다시 오면 오늘 줄이 추가된다
    db.query(UserDailyVisit).filter(UserDailyVisit.user_id == user.id).delete()
    db.add(UserDailyVisit(user_id=user.id, visit_date=kst_today() - timedelta(days=1)))
    user = _user(db, "a@hufs.ac.kr")
    user.last_active_at = utcnow() - timedelta(days=1)
    db.commit()
    client.get("/api/v1/me/profile")
    assert sorted(v.visit_date for v in _visits(db, user.id)) == [kst_today() - timedelta(days=1), kst_today()]


def test_dashboard_active_means_visited_in_last_7_days(sent_codes, db):
    signup(sent_codes, db, "m@hufs.ac.kr", gender="MALE")
    signup(sent_codes, db, "f@hufs.ac.kr", gender="FEMALE")
    signup(sent_codes, db, "old@hufs.ac.kr", gender="FEMALE")

    # old는 10일 전에 마지막으로 왔다
    old = _user(db, "old@hufs.ac.kr")
    db.query(UserDailyVisit).filter(UserDailyVisit.user_id == old.id).delete()
    db.add(UserDailyVisit(user_id=old.id, visit_date=kst_today() - timedelta(days=10)))
    old.last_active_at = utcnow() - timedelta(days=10)
    db.commit()

    stats = admin_login(db).get("/api/v1/admin/dashboard").json()
    assert stats["users_total"] == 3
    assert stats["users_normal"] == 3
    assert stats["users_active"] == 2  # old는 빠진다
    assert stats["users_active_today"] == 2
    assert stats["users_male"] == 1
    assert stats["users_female"] == 2


def test_admin_user_list_gender_filter(sent_codes, db):
    signup(sent_codes, db, "m@hufs.ac.kr", gender="MALE")
    signup(sent_codes, db, "f@hufs.ac.kr", gender="FEMALE")
    admin = admin_login(db)

    rows = admin.get("/api/v1/admin/users").json()["users"]
    assert {r["nickname"]: r["gender"] for r in rows} == {"user_m": "MALE", "user_f": "FEMALE"}

    males = admin.get("/api/v1/admin/users?gender=MALE").json()["users"]
    assert [r["nickname"] for r in males] == ["user_m"]
    females = admin.get("/api/v1/admin/users?gender=FEMALE").json()["users"]
    assert [r["nickname"] for r in females] == ["user_f"]

    assert admin.get("/api/v1/admin/users?gender=OTHER").status_code == 422


def test_frequent_visitor_is_recommended_first(sent_codes, db):
    admin = admin_login(db)
    viewer = ready_user(sent_codes, db, admin, "viewer@hufs.ac.kr", gender="MALE", want="FEMALE")
    # 먼저 가입한 사람(rare)과 나중에 가입한 사람(frequent). 다른 점수는 같다.
    rare = ready_user(sent_codes, db, admin, "rare@hufs.ac.kr", gender="FEMALE", want="MALE")
    frequent = ready_user(sent_codes, db, admin, "frequent@hufs.ac.kr", gender="FEMALE", want="MALE")

    user = _user(db, "frequent@hufs.ac.kr")
    for d in range(1, 10):  # 최근 9일 더 접속
        db.add(UserDailyVisit(user_id=user.id, visit_date=kst_today() - timedelta(days=d)))
    db.commit()

    for _ in range(5):
        assert discover_ids(viewer)[:2] == [frequent.profile_id, rare.profile_id]
