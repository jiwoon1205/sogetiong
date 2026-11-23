"""공지 팝업 (2026-10-05, 2026-10-25부터 하루 한 번).

- /me에 아직 안 본 공지 이름이 나온다 (DAILY면 이름 뒤에 "@한국 날짜").
- "확인"을 누르면 그날은 그 계정에 다시 안 나온다 (다른 기기에서 로그인해도). 다음 날 다시 한 번 나온다.
- 지금 공지가 아닌 이름은 받지 않는다. 공지를 끄면(None) 아무것도 안 나온다.
"""

from app.models.user import User
import pytest

from app.services import announcement_service


@pytest.fixture(autouse=True)
def _show_to_everyone(monkeypatch):
    """테스트 계정은 지금 막 가입한 "신규 가입자"라 공지가 안 뜬다 → 신규 가입자 제외는 따로 시험한다."""
    monkeypatch.setattr(announcement_service, "CURRENT_FOR_JOINED_BEFORE", None)

from tests.conftest import UserClient, signup


def test_shown_once_per_account(sent_codes, db, monkeypatch):
    monkeypatch.setattr(announcement_service, "DAILY", False)  # 예전 방식(계정당 한 번)도 그대로 동작
    monkeypatch.setattr(announcement_service, "CURRENT", "test-notice")  # 지금은 공지가 꺼져 있어서(2026-11-14) 시험용 이름
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
    monkeypatch.setattr(announcement_service, "DAILY", False)
    monkeypatch.setattr(announcement_service, "CURRENT", "test-notice")
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    a.post("/api/v1/me/announcement/seen", json={"key": announcement_service.CURRENT})
    monkeypatch.setattr(announcement_service, "CURRENT", "next-notice")
    assert a.get("/api/v1/me").json()["announcement"] == "next-notice"
    monkeypatch.setattr(announcement_service, "CURRENT", None)
    assert a.get("/api/v1/me").json()["announcement"] is None


def test_notice_shown_once_a_day(sent_codes, db, monkeypatch):
    """2026-10-25: 공지는 하루 한 번. 오늘 확인하면 오늘은 안 뜨고, 다음 날 다시 뜬다."""
    from datetime import timedelta

    monkeypatch.setattr(announcement_service, "CURRENT", "test-notice")
    monkeypatch.setattr(announcement_service, "DAILY", True)  # 2026-11-14부터 기본은 계정당 한 번

    from app.core.time import kst_today, utcnow

    a = signup(sent_codes, db, "a@hufs.ac.kr")
    key = a.get("/api/v1/me").json()["announcement"]
    assert key == f"{announcement_service.CURRENT}@{kst_today().isoformat()}"
    assert a.post("/api/v1/me/announcement/seen", json={"key": announcement_service.CURRENT}).status_code == 404  # 날짜 없는 이름은 안 받음
    assert a.post("/api/v1/me/announcement/seen", json={"key": key}).status_code == 200
    assert a.get("/api/v1/me").json()["announcement"] is None

    db.expire_all()
    user = db.query(User).filter(User.email == "a@hufs.ac.kr").one()
    tomorrow = utcnow() + timedelta(days=1)
    assert announcement_service.pending(user, tomorrow) == f"{announcement_service.CURRENT}@{kst_today(tomorrow).isoformat()}"


# ---------- 결제 오픈 공지: 하루 한 번, 정식 배포 전까지 (2026-10-06) ----------

from datetime import timedelta  # noqa: E402

from app.core.time import utcnow  # noqa: E402
from tests.conftest import admin_login, ready_user  # noqa: E402
from tests.test_membership import paid_world, pay, switch_on  # noqa: E402,F401  (fixture)


def _daily(monkeypatch, s, *, opens_in=timedelta(days=1)):
    switch_on(monkeypatch, s, vip=True)
    monkeypatch.setattr(s, "open_at", utcnow() + opens_in)


def test_all_notices_off_now(sent_codes, db, monkeypatch):
    """2026-11-22: 공지 팝업을 모두 끔 (사용자 결정). 새 학교가 열려 있어도 안 뜬다."""
    from app.core.config import get_settings

    assert announcement_service.CURRENT is None
    assert announcement_service.SCHOOL_OPEN_NOTICE is None
    assert announcement_service.NEW_SCHOOLS_NOTICE is None
    monkeypatch.setattr(get_settings(), "open_schools", "hufs.ac.kr,khu.ac.kr,korea.ac.kr")
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    assert a.get("/api/v1/me").json()["announcement"] is None


def test_chat_extras_notice_once_per_account(sent_codes, db, monkeypatch):
    """계정당 한 번 (2026-11-14 방식). 2026-11-22부터 꺼져 있어서 시험용으로 켠다."""
    monkeypatch.setattr(announcement_service, "CURRENT", "chat-extras-2026-11")
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    assert announcement_service.DAILY is False
    assert a.get("/api/v1/me").json()["announcement"] == "chat-extras-2026-11"
    assert a.post("/api/v1/me/announcement/seen", json={"key": "chat-extras-2026-11"}).status_code == 200
    assert a.get("/api/v1/me").json()["announcement"] is None


def test_seen_in_daily_mode_counts_as_seen(sent_codes, db, monkeypatch):
    monkeypatch.setattr(announcement_service, "CURRENT", "chat-extras-2026-11")
    """하루 한 번 방식일 때(이름@날짜) 이미 본 사람에게는 계정당 한 번 방식으로 바꿔도 다시 안 뜬다."""
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    db.query(User).filter(User.email == "a@hufs.ac.kr").update({"announcement_seen": "chat-extras-2026-11@2026-11-14"})
    db.commit()
    assert a.get("/api/v1/me").json()["announcement"] is None
    # 다른 공지를 본 기록이면 뜬다
    db.query(User).filter(User.email == "a@hufs.ac.kr").update({"announcement_seen": "female-free-2026-11@2026-11-13"})
    db.commit()
    assert a.get("/api/v1/me").json()["announcement"] == "chat-extras-2026-11"


def test_new_signups_do_not_get_feature_notice(sent_codes, db, monkeypatch):
    """2026-11-14: 기준 시각 이후 가입한 계정에는 기능 소개 공지가 안 뜬다. 그 전 가입자에게는 뜬다."""
    from datetime import timedelta

    from app.core.time import utcnow

    monkeypatch.setattr(announcement_service, "CURRENT", "chat-extras-2026-11")
    monkeypatch.setattr(announcement_service, "CURRENT_FOR_JOINED_BEFORE", utcnow() - timedelta(minutes=1))
    monkeypatch.setattr(announcement_service, "KHU_VIP_NOTICE", None)  # 하루 한 번 뜨는 초대 이벤트 공지는 빼고 확인
    new = signup(sent_codes, db, "new@hufs.ac.kr")
    assert new.get("/api/v1/me").json()["announcement"] is None

    old = signup(sent_codes, db, "old@hufs.ac.kr")
    db.query(User).filter(User.email == "old@hufs.ac.kr").update({"created_at": utcnow() - timedelta(days=3)})
    db.commit()
    assert old.get("/api/v1/me").json()["announcement"] == "chat-extras-2026-11"


def test_payment_notice_once_a_day_before_open(sent_codes, db, paid_world, monkeypatch):
    from app.core import time as time_mod

    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr", gender="MALE", want="FEMALE")
    _daily(monkeypatch, paid_world)
    key = a.get("/api/v1/me").json()["announcement"]
    assert key and key.startswith(announcement_service.PAYMENT_DAILY_PREFIX)
    assert a.post("/api/v1/me/announcement/seen", json={"key": key}).status_code == 200
    # 오늘 하루 공지는 끝 (2026-10-24: 그 뒤에는 한 번 공지가 뜰 수 있다 → 결제 공지만 아니면 된다)
    assert not (a.get("/api/v1/me").json()["announcement"] or "").startswith(announcement_service.PAYMENT_DAILY_PREFIX)

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
    assert not (announcement_service.pending(user, night) or "").startswith(announcement_service.PAYMENT_DAILY_PREFIX)
    # 오후에 "봤음"으로 보내는 이름도 받아준다
    assert announcement_service.is_showable(user, k_pm, pm)
