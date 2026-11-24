"""관리자 → 공지 팝업 (2026-11-24): 진행 상황 · 켜기/끄기."""

from datetime import timedelta

from app.core.time import utcnow
from app.models.admin import AuditLog
from app.models.user import User
from tests.conftest import admin_login, ready_user, signup


def _yesterday(db, email):
    db.expire_all()
    u = db.query(User).filter(User.email == email).one()
    u.created_at = utcnow() - timedelta(days=1)
    db.commit()


def test_toggle_invite_and_install_popups(sent_codes, db):
    admin = admin_login(db)
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    _yesterday(db, "a@hufs.ac.kr")
    me = a.get("/api/v1/me").json()
    assert me["announcement"].startswith("khu-vip10@") and me["install_popup"] is True

    assert admin.put("/api/v1/admin/popups/invite", json={"enabled": False}).status_code == 200
    assert admin.put("/api/v1/admin/popups/install", json={"enabled": False}).status_code == 200
    me = a.get("/api/v1/me").json()
    assert me["announcement"] is None and me["install_popup"] is False
    assert admin.put("/api/v1/admin/popups/nope", json={"enabled": False}).status_code == 404
    assert [l.action for l in db.query(AuditLog).filter(AuditLog.target_type == "POPUP")] == ["POPUP_OFF", "POPUP_OFF"]

    assert admin.put("/api/v1/admin/popups/invite", json={"enabled": True}).status_code == 200
    assert a.get("/api/v1/me").json()["announcement"].startswith("khu-vip10@")


def test_popup_progress(sent_codes, db):
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr")
    _yesterday(db, "a@hufs.ac.kr")
    key = a.get("/api/v1/me").json()["announcement"]
    assert a.post("/api/v1/me/announcement/seen", json={"key": key}).status_code == 200
    assert a.post("/api/v1/me/install-popup/seen").status_code == 200
    a.post("/api/v1/me/app-open", json={"platform": "IOS"})
    body = admin.get("/api/v1/admin/popups").json()
    assert body["invite"]["enabled"] is True and body["invite"]["seen_today"] == 1 and body["invite"]["goal"] == 10
    assert body["install"]["seen_3days"] == 1 and body["install"]["app_users"] == 1 and body["install"]["active_users"] == 1
    assert body["survey"]["open"] is True


def test_popups_permission(sent_codes, db):
    mod = admin_login(db, role="MODERATOR")
    assert mod.put("/api/v1/admin/popups/invite", json={"enabled": False}).status_code == 403
