"""한 번만 보여주는 공지 팝업 (2026-10-05).

- /me에 아직 안 본 공지 이름이 나온다.
- "확인"을 누르면 그 계정에는 다시 안 나온다 (다른 기기에서 로그인해도).
- 지금 공지가 아닌 이름은 받지 않는다. 공지를 끄면(None) 아무것도 안 나온다.
"""

from app.models.user import User
from app.services import announcement_service

from tests.conftest import UserClient, signup


def test_shown_once_per_account(sent_codes, db):
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    key = announcement_service.CURRENT
    assert a.get("/api/v1/me").json()["announcement"] == key

    assert a.post("/api/v1/me/announcement/seen", json={"key": "old-one"}).status_code == 404
    r = a.post("/api/v1/me/announcement/seen", json={"key": key})
    assert r.status_code == 200
    assert a.get("/api/v1/me").json()["announcement"] is None

    # 다른 기기(새 로그인)에서도 다시 안 뜬다
    other = UserClient()
    assert other.post("/api/v1/auth/login", json={"email": "a@hufs.ac.kr", "password": "goodpass123"}).status_code == 200
    assert other.get("/api/v1/me").json()["announcement"] is None


def test_new_announcement_shows_again_and_can_be_off(sent_codes, db, monkeypatch):
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    a.post("/api/v1/me/announcement/seen", json={"key": announcement_service.CURRENT})
    monkeypatch.setattr(announcement_service, "CURRENT", "next-notice")
    assert a.get("/api/v1/me").json()["announcement"] == "next-notice"
    monkeypatch.setattr(announcement_service, "CURRENT", None)
    assert a.get("/api/v1/me").json()["announcement"] is None


# ---------- 결제 오픈 공지: 하루 한 번, 정식 배포 전까지 (2026-10-06) ----------

from datetime import timedelta  # noqa: E402

from app.core.time import utcnow  # noqa: E402
from tests.conftest import admin_login, ready_user  # noqa: E402
from tests.test_membership import paid_world, pay, switch_on  # noqa: E402,F401  (fixture)


def _daily(monkeypatch, s, *, opens_in=timedelta(days=1)):
    switch_on(monkeypatch, s, vip=True)
    monkeypatch.setattr(s, "open_at", utcnow() + opens_in)


def test_payment_notice_once_a_day_before_open(sent_codes, db, paid_world, monkeypatch):
    from app.core import time as time_mod

    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr", gender="MALE", want="FEMALE")
    _daily(monkeypatch, paid_world)
    key = a.get("/api/v1/me").json()["announcement"]
    assert key and key.startswith(announcement_service.PAYMENT_DAILY_PREFIX)
    assert a.post("/api/v1/me/announcement/seen", json={"key": key}).status_code == 200
    assert a.get("/api/v1/me").json()["announcement"] is None  # 오늘은 끝 (예전 한 번 공지도 다시 안 뜸)

    # 다음 날이 되면 다시 뜬다
    tomorrow = time_mod.kst_today() + timedelta(days=1)
    monkeypatch.setattr("app.services.announcement_service.kst_today", lambda now=None: tomorrow)
    nxt = a.get("/api/v1/me").json()["announcement"]
    assert nxt.startswith(f"{announcement_service.PAYMENT_DAILY_PREFIX}{tomorrow.isoformat()}") and nxt != key


def test_payment_notice_hidden_after_open_or_purchase(sent_codes, db, paid_world, monkeypatch):
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr", gender="MALE", want="FEMALE")
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr", gender="FEMALE", want="MALE")
    _daily(monkeypatch, paid_world)
    pay(admin, b)  # 산 사람에게는 안 뜬다
    assert not (b.get("/api/v1/me").json()["announcement"] or "").startswith(announcement_service.PAYMENT_DAILY_PREFIX)
    # 정식 배포가 지나면 안 뜬다
    monkeypatch.setattr(paid_world, "open_at", utcnow() - timedelta(seconds=1))
    assert not (a.get("/api/v1/me").json()["announcement"] or "").startswith(announcement_service.PAYMENT_DAILY_PREFIX)
    # 판매를 안 하면 안 뜬다
    monkeypatch.setattr(paid_world, "open_at", utcnow() + timedelta(days=1))
    monkeypatch.setattr(paid_world, "membership_enabled", False)
    monkeypatch.setattr(paid_world, "vip_enabled", False)
    assert not (a.get("/api/v1/me").json()["announcement"] or "").startswith(announcement_service.PAYMENT_DAILY_PREFIX)


def test_payment_notice_again_from_3pm(sent_codes, db, paid_world, monkeypatch):
    """한국 시간 오후 3시부터는 오전에 본 사람에게도 한 번 더 뜬다 (2026-10-07)."""
    from app.core.time import KST
    from datetime import datetime

    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr", gender="MALE", want="FEMALE")
    _daily(monkeypatch, paid_world)
    user = db.query(User).filter(User.email == "a@hufs.ac.kr").one()
    monkeypatch.setattr(paid_world, "open_at", datetime(2026, 10, 8, tzinfo=KST))
    am = datetime(2026, 10, 7, 11, 0, tzinfo=KST)
    before3 = datetime(2026, 10, 7, 14, 59, tzinfo=KST)
    pm = datetime(2026, 10, 7, 15, 0, tzinfo=KST)
    night = datetime(2026, 10, 7, 23, 59, tzinfo=KST)
    k_am = announcement_service.daily_payment_key(user, am)
    assert k_am == "payment-open:2026-10-07"
    assert announcement_service.daily_payment_key(user, before3) == k_am
    k_pm = announcement_service.daily_payment_key(user, pm)
    assert k_pm == "payment-open:2026-10-07-15" and k_pm != k_am
    assert announcement_service.daily_payment_key(user, night) == k_pm
    # 오전에 봤어도 오후 3시부터 다시 뜨고, 오후 공지를 보면 그날은 끝
    user.announcement_seen = k_am
    assert announcement_service.pending(user, pm) == k_pm
    user.announcement_seen = k_pm
    assert announcement_service.pending(user, night) is None
    # 오후에 "봤음"으로 보내는 이름도 받아준다
    assert announcement_service.is_showable(user, k_pm, pm)
