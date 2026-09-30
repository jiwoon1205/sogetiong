"""마지막 접속 시각 (관리자 화면용, 2026-10-01).

- 가입·로그인하면 기록된다.
- 사이트를 쓰는 동안 10분에 한 번씩 갱신된다 (매 요청마다 DB에 쓰지 않는다).
- 로그아웃해도 남는다 (세션과 따로 저장).
"""

from datetime import timedelta

from app.core.time import as_utc, utcnow
from app.models.user import User

from tests.conftest import UserClient, admin_login, signup


def _user(db, email):
    db.expire_all()
    return db.query(User).filter(User.email == email).one()


def test_last_active_recorded_and_throttled(sent_codes, db):
    client = signup(sent_codes, db, "a@hufs.ac.kr")
    first = _user(db, "a@hufs.ac.kr").last_active_at
    assert first is not None  # 가입 = 접속

    # 10분 안에 다시 쓰면 그대로 (DB 쓰기 절약)
    client.get("/api/v1/me/profile")
    assert _user(db, "a@hufs.ac.kr").last_active_at == first

    # 10분이 지난 뒤 쓰면 갱신
    user = _user(db, "a@hufs.ac.kr")
    user.last_active_at = utcnow() - timedelta(minutes=11)
    db.commit()
    client.get("/api/v1/me/profile")
    assert utcnow() - as_utc(_user(db, "a@hufs.ac.kr").last_active_at) < timedelta(minutes=1)

    # 로그아웃해도 기록은 남는다
    assert client.post("/api/v1/auth/logout").status_code == 200
    assert _user(db, "a@hufs.ac.kr").last_active_at is not None


def test_login_updates_last_active(sent_codes, db):
    signup(sent_codes, db, "b@hufs.ac.kr")
    user = _user(db, "b@hufs.ac.kr")
    user.last_active_at = utcnow() - timedelta(days=3)
    db.commit()
    r = UserClient().post("/api/v1/auth/login", json={"email": "b@hufs.ac.kr", "password": "goodpass123"})
    assert r.status_code == 200, r.text
    assert utcnow() - as_utc(_user(db, "b@hufs.ac.kr").last_active_at) < timedelta(minutes=1)


def test_admin_sees_last_active(sent_codes, db):
    signup(sent_codes, db, "c@hufs.ac.kr")
    admin = admin_login(db)
    rows = admin.get("/api/v1/admin/users").json()["users"]
    row = next(u for u in rows if u["nickname"] == "user_c")
    assert row["last_active_at"] is not None
    detail = admin.get(f"/api/v1/admin/users/{row['user_id']}").json()
    assert detail["last_active_at"] == row["last_active_at"]
