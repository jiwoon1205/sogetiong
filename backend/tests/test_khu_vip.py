"""친구 10명 초대 → 평생 VIP (2026-11-22 경희대생 전용 → 2026-11-24 모든 사용자).

- 모든 사용자에게 공지 팝업(하루 한 번, 가입한 날은 빼고)과 진행 상황이 보인다
- 내 링크로 가입한 친구(학교 상관없음)가 사진 검수를 통과해야 1명 인정
- 평생 VIP가 걸린 직후부터 센다: 경희대생은 11-22, 나머지는 11-24. 그 전 초대는 안 셈
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
    monkeypatch.setattr(khu_vip_service, "KHU_START", utcnow() - timedelta(hours=2))
    monkeypatch.setattr(khu_vip_service, "START", utcnow() - timedelta(hours=1))
    monkeypatch.setattr(khu_vip_service, "GOAL", goal)
    _open_khu(monkeypatch, db)


def _approve_khu(client, db, admin):
    choose_department(client, db, "정치외교학과", school=KHU)
    set_preferences(client)
    approve(admin, upload_photo(client))


def _approve_hufs(client, db, admin):
    choose_department(client, db, "경영학부")
    set_preferences(client)
    approve(admin, upload_photo(client))


def _user(db, email):
    db.expire_all()
    return db.query(User).filter(User.email == email).one()


def _joined_yesterday(db, email):
    u = _user(db, email)
    u.created_at = utcnow() - timedelta(days=1)
    db.commit()


def _set_created(db, email, when):
    u = _user(db, email)
    u.created_at = when
    db.commit()


def test_popup_for_everyone_from_next_visit_day(monkeypatch, sent_codes, db):
    _setup(monkeypatch, db)
    admin_login(db)
    k = signup(sent_codes, db, "k@khu.ac.kr", school=KHU)
    h = signup(sent_codes, db, "h@hufs.ac.kr")
    # 가입한 날에는 안 뜬다
    assert h.get("/api/v1/me").json()["announcement"] is None
    assert h.get("/api/v1/me").json()["khu_vip"]["count"] == 0
    _joined_yesterday(db, "k@khu.ac.kr")
    _joined_yesterday(db, "h@hufs.ac.kr")
    for c in (k, h):
        key = c.get("/api/v1/me").json()["announcement"]
        assert key.startswith("khu-vip10@")
        # 오늘은 그만 보기 → 오늘은 안 뜸
        assert c.post("/api/v1/me/announcement/seen", json={"key": key}).status_code == 200
        assert c.get("/api/v1/me").json()["announcement"] is None


def test_any_school_invites_count_after_start(monkeypatch, sent_codes, db):
    _setup(monkeypatch, db, goal=2)
    admin = admin_login(db)
    h = signup(sent_codes, db, "h@hufs.ac.kr")
    code = _code(h)

    # 이벤트가 걸리기 전에 가입한 초대는 안 셈
    old = _signup_with(sent_codes, db, "old@hufs.ac.kr", code)
    _set_created(db, "old@hufs.ac.kr", khu_vip_service.START - timedelta(minutes=5))
    _approve_hufs(old, db, admin)
    assert h.get("/api/v1/me").json()["khu_vip"]["count"] == 0

    # 가입만 하고 사진 검수 전이면 안 셈 → 검수 끝나면 1명 (외대생)
    a = _signup_with(sent_codes, db, "a@hufs.ac.kr", code)
    assert h.get("/api/v1/me").json()["khu_vip"]["count"] == 0
    _approve_hufs(a, db, admin)
    assert h.get("/api/v1/me").json()["khu_vip"]["count"] == 1
    assert not vip_service.has_paid_vip(_user(db, "h@hufs.ac.kr"))

    # 다른 학교(경희대) 친구도 셈 → 2명 = 평생 VIP
    k = _signup_with(sent_codes, db, "k@khu.ac.kr", code, school=KHU)
    _approve_khu(k, db, admin)
    me = _user(db, "h@hufs.ac.kr")
    assert khu_vip_service.has_lifetime(me) and vip_service.is_vip(me) and membership_service.has_membership(me)
    assert db.query(Notification).filter(Notification.user_id == me.id, Notification.type == "VIP_LIFETIME").count() == 1
    assert db.query(AuditLog).filter(AuditLog.action == "KHU_VIP_LIFETIME").count() == 1
    _joined_yesterday(db, "h@hufs.ac.kr")
    body = h.get("/api/v1/me").json()
    assert body["khu_vip"]["done"] is True and body["announcement"] is None


def test_khu_students_keep_count_from_nov_22(monkeypatch, sent_codes, db):
    """경희대생은 11-22(경희대 전용으로 걸린 때)부터 센 숫자가 그대로 이어진다. 다른 학교 학생은 11-24부터."""
    _setup(monkeypatch, db, goal=5)
    admin = admin_login(db)
    k = signup(sent_codes, db, "k@khu.ac.kr", school=KHU)
    h = signup(sent_codes, db, "h@hufs.ac.kr")
    between = khu_vip_service.START - timedelta(minutes=30)  # 11-22 와 11-24 사이에 가입한 초대
    for inviter, email in ((k, "k1@khu.ac.kr"), (h, "h1@khu.ac.kr")):
        c = _signup_with(sent_codes, db, email, _code(inviter), school=KHU)
        _set_created(db, email, between)
        _approve_khu(c, db, admin)
    assert k.get("/api/v1/me").json()["khu_vip"]["count"] == 1
    assert h.get("/api/v1/me").json()["khu_vip"]["count"] == 0
