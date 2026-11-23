"""앱(홈 화면 아이콘)으로 연 기록과 관리자 현황 (2026-11-24)."""

from app.models.user import User
from tests.conftest import admin_login, ready_user


def test_app_open_counts_in_dashboard(sent_codes, db):
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr")
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr")
    ready_user(sent_codes, db, admin, "c@hufs.ac.kr")
    assert a.post("/api/v1/me/app-open", json={"platform": "IOS"}).status_code == 200
    assert b.post("/api/v1/me/app-open", json={"platform": "ANDROID"}).status_code == 200
    assert b.post("/api/v1/me/app-open", json={"platform": "PHONE"}).status_code == 422
    db.expire_all()
    assert db.query(User).filter(User.email == "a@hufs.ac.kr").one().app_platform == "IOS"
    body = admin.get("/api/v1/admin/dashboard").json()
    assert body["app_users"] == {"total": 2, "ios": 1, "android": 1, "desktop": 0}
    assert body["users_active"] == 3 and body["app_users_total"] == 2
