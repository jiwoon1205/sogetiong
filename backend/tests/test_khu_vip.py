"""경희대생 전용: 경희대 친구 10명 초대 → 평생 VIP (2026-11-22).

- 경희대 학생에게만 공지 팝업(하루 한 번)과 진행 상황이 보인다
- 내 링크로 가입한 경희대 학생이 사진 검수를 통과해야 1명 인정. 외대생 초대·이벤트 전 초대는 안 셈
- 10명이 되면 자동 평생 VIP (기본 이용권 포함) + 알림 + 감사 로그. 그 뒤 공지는 안 뜸
"""

from datetime import timedelta

from app.core.config import get_settings
from app.core.time import utcnow
from app.models.admin import AuditLog
from app.models.matching import Notification
from app.models.user import User
from app.services import khu_vip_service, membership_service, vip_service
from tests.conftest import admin_login, approve, choose_department, set_preferences, signup, upload_photo
from tests.test_referral import _code, _signup_with
from tests.test_schools import KHU, _open_khu


def _setup(monkeypatch, db, goal=2):
    s = get_settings()
    monkeypatch.setattr(s, "referral_schools", "")
    monkeypatch.setattr(s, "referral_start", utcnow() - timedelta(days=1))
    monkeypatch.setattr(khu_vip_service, "START", utcnow() - timedelta(hours=1))
    monkeypatch.setattr(khu_vip_service, "GOAL", goal)
    _open_khu(monkeypatch, db)


def _approve_khu(client, db, admin):
    choose_department(client, db, "정치외교학과", school=KHU)
    set_preferences(client)
    approve(admin, upload_photo(client))


def _user(db, email):
    db.expire_all()
    return db.query(User).filter(User.email == email).one()


def _joined_yesterday(db, email):
    u = _user(db, email)
    u.created_at = utcnow() - timedelta(days=1)
    db.commit()


def test_new_signup_sees_popup_from_next_visit_day(monkeypatch, sent_codes, db):
    """가입한 날에는 안 뜨고, 다음 날 접속부터 뜬다 (2026-11-22)."""
    _setup(monkeypatch, db)
    admin_login(db)
    k = signup(sent_codes, db, "k@khu.ac.kr", school=KHU)
    me = k.get("/api/v1/me").json()
    assert me["khu_vip"]["count"] == 0 and me["announcement"] is None
    _joined_yesterday(db, "k@khu.ac.kr")
    assert k.get("/api/v1/me").json()["announcement"].startswith("khu-vip10@")


def test_popup_only_for_khu_students(monkeypatch, sent_codes, db):
    _setup(monkeypatch, db)
    admin_login(db)
    k = signup(sent_codes, db, "k@khu.ac.kr", school=KHU)
    h = signup(sent_codes, db, "h@hufs.ac.kr")
    _joined_yesterday(db, "k@khu.ac.kr")
    _joined_yesterday(db, "h@hufs.ac.kr")
    me = k.get("/api/v1/me").json()
    assert me["khu_vip"] == {"count": 0, "goal": 2, "done": False}
    key = me["announcement"]
    assert key.startswith("khu-vip10@")
    assert h.get("/api/v1/me").json()["khu_vip"] is None
    assert h.get("/api/v1/me").json()["announcement"] is None
    # 오늘은 그만 보기 → 오늘은 안 뜸
    assert k.post("/api/v1/me/announcement/seen", json={"key": key}).status_code == 200
    assert k.get("/api/v1/me").json()["announcement"] is None
    assert h.post("/api/v1/me/announcement/seen", json={"key": key}).status_code == 404


def test_ten_khu_invites_give_lifetime_vip(monkeypatch, sent_codes, db):
    _setup(monkeypatch, db, goal=2)
    admin = admin_login(db)
    k = signup(sent_codes, db, "k@khu.ac.kr", school=KHU)
    code = _code(k)

    # 외대생 초대는 안 셈
    h = _signup_with(sent_codes, db, "h@hufs.ac.kr", code)
    choose_department(h, db, "경영학부")
    set_preferences(h)
    approve(admin, upload_photo(h))
    # 이벤트 전에 가입한 경희대생 초대도 안 셈
    old = _signup_with(sent_codes, db, "old@khu.ac.kr", code, school=KHU)
    u = _user(db, "old@khu.ac.kr")
    u.created_at = khu_vip_service.START - timedelta(minutes=5)
    db.commit()
    _approve_khu(old, db, admin)
    assert k.get("/api/v1/me").json()["khu_vip"]["count"] == 0

    # 가입만 하고 사진 검수 전이면 안 셈
    k1 = _signup_with(sent_codes, db, "k1@khu.ac.kr", code, school=KHU)
    assert k.get("/api/v1/me").json()["khu_vip"]["count"] == 0
    _approve_khu(k1, db, admin)
    assert k.get("/api/v1/me").json()["khu_vip"] == {"count": 1, "goal": 2, "done": False}
    assert not vip_service.has_paid_vip(_user(db, "k@khu.ac.kr"))

    k2 = _signup_with(sent_codes, db, "k2@khu.ac.kr", code, school=KHU)
    _approve_khu(k2, db, admin)
    me = _user(db, "k@khu.ac.kr")
    assert khu_vip_service.has_lifetime(me) and vip_service.is_vip(me) and membership_service.has_membership(me)
    assert db.query(Notification).filter(Notification.user_id == me.id, Notification.type == "VIP_LIFETIME").count() == 1
    assert db.query(AuditLog).filter(AuditLog.action == "KHU_VIP_LIFETIME").count() == 1
    body = k.get("/api/v1/me").json()
    assert body["khu_vip"]["done"] is True and body["announcement"] is None


def test_non_khu_referrer_gets_nothing(monkeypatch, sent_codes, db):
    _setup(monkeypatch, db, goal=1)
    admin = admin_login(db)
    h = signup(sent_codes, db, "h@hufs.ac.kr")
    k1 = _signup_with(sent_codes, db, "k1@khu.ac.kr", _code(h), school=KHU)
    _approve_khu(k1, db, admin)
    assert not khu_vip_service.has_lifetime(_user(db, "h@hufs.ac.kr"))
