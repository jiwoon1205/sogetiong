"""점검 기간 (2026-10-04, `점검 기간 설계`).

- OPEN_AT 전에는 추천·LIKE·PASS·받은 LIKE·기존 회원 사진 재검토를 막는다 (409 MAINTENANCE)
- 대화와 결제(이용권·VIP)는 된다. 새 가입자는 결제·첫 사진 제출까지 된다
- 점검 기간에 낸 이용권·VIP·쌓아 둔 일수는 오픈 시각부터 28일
- OPEN_AT이 지나면 자동으로 열린다. OPEN_AT이 없으면 원래 동작
"""

from datetime import timedelta

import pytest

from app.core.config import Settings, get_settings
from app.core.time import as_utc, utcnow
from app.services import membership_service
from tests.conftest import admin_login, ready_user
from tests.test_membership import (  # noqa: F401  (fixture)
    blank_user,
    can_start,
    kst,
    kst_midnight_after,
    make_match,
    paid_world,
    pay,
    switch_on,
    user_of,
)

OPEN = kst(2026, 10, 10, 18)


@pytest.fixture
def maint(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "membership_enabled", True)
    monkeypatch.setattr(s, "vip_test_emails", "")
    monkeypatch.setattr(s, "open_at", OPEN)
    return s


# ---------- 설정 ----------


def test_open_at_without_timezone_is_kst(monkeypatch):
    monkeypatch.setenv("OPEN_AT", "2026-10-10T18:00:00")
    assert Settings().open_at_utc == OPEN
    monkeypatch.setenv("OPEN_AT", "")
    assert Settings().open_at_utc is None


# ---------- 날짜 계산 (DB 없이) ----------


def test_before_open(maint):
    assert membership_service.before_open(kst(2026, 10, 9)) is True
    assert membership_service.before_open(OPEN) is False
    assert membership_service.before_open(kst(2026, 10, 11)) is False


def test_payment_during_maintenance_starts_at_open(maint, can_start):
    u = blank_user()
    membership_service.add_membership(None, u, kst(2026, 10, 9))
    # 10/10 18시 + 28일 = 11/7 18시 → 11/7 밤 12시
    assert as_utc(u.member_until) == kst_midnight_after(2026, 11, 7)


def test_vip_during_maintenance_starts_at_open(maint, can_start):
    u = blank_user()
    membership_service.add_vip(None, u, kst(2026, 10, 8, 20))
    assert as_utc(u.vip_until) == kst_midnight_after(2026, 11, 7)
    assert as_utc(u.member_until) == kst_midnight_after(2026, 11, 7)
    # 점검 기간에 기본을 하나 더 사면 VIP 뒤로 이어진다
    membership_service.add_membership(None, u, kst(2026, 10, 9))
    assert as_utc(u.member_until) == kst_midnight_after(2026, 12, 5)


def test_banked_days_started_during_maintenance_count_from_open(maint, can_start):
    can_start["value"] = False
    u = blank_user()
    membership_service.add_membership(None, u, kst(2026, 10, 8, 20))
    assert u.member_days_banked == 28
    can_start["value"] = True
    assert membership_service.start_banked(None, u, kst(2026, 10, 9)) is True  # 점검 중 사진 승인
    assert as_utc(u.member_until) == kst_midnight_after(2026, 11, 7)


def test_after_open_counts_from_now(maint, can_start):
    u = blank_user()
    membership_service.add_membership(None, u, kst(2026, 10, 12))
    assert as_utc(u.member_until) == kst_midnight_after(2026, 11, 9)


def test_no_open_at_keeps_old_rule(maint, can_start, monkeypatch):
    monkeypatch.setattr(maint, "open_at", None)
    u = blank_user()
    membership_service.add_membership(None, u, kst(2026, 10, 9))
    assert as_utc(u.member_until) == kst_midnight_after(2026, 11, 6)
    assert membership_service.before_open(kst(2026, 10, 9)) is False


# ---------- API ----------


def open_in(monkeypatch, s, delta: timedelta):
    monkeypatch.setattr(s, "open_at", utcnow() + delta)


def test_maintenance_blocks_matching_but_not_chat_or_payment(sent_codes, db, paid_world, monkeypatch):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    her = ready_user(sent_codes, db, admin, "her@hufs.ac.kr", gender="FEMALE", want="MALE")
    match_id = make_match(me, her)
    switch_on(monkeypatch, paid_world, vip=True)
    open_in(monkeypatch, paid_world, timedelta(days=2))

    # 이용권이 없어도 있어도 점검 중에는 MAINTENANCE
    for r in (
        me.get("/api/v1/discover"),
        me.get("/api/v1/liked-me"),
        me.post("/api/v1/likes", json={"profile_id": her.profile_id}),
        me.post("/api/v1/passes", json={"profile_id": her.profile_id}),
        me.delete(f"/api/v1/passes/{her.profile_id}"),
    ):
        assert r.status_code == 409 and r.json()["detail"] == "MAINTENANCE", r.text

    # 결제는 된다 → 오픈 시각부터 28일
    pay(admin, me)
    user = user_of(db, me)
    open_at = as_utc(paid_world.open_at)
    assert as_utc(user.member_until) == membership_service.end_of_kst_day(open_at + timedelta(days=28))
    m = me.get("/api/v1/me").json()["membership"]
    assert m["before_open"] is True and m["open_at"] is not None and m["status"] == "active"
    assert me.get("/api/v1/discover").json()["detail"] == "MAINTENANCE"

    # VIP도 살 수 있다
    pay(admin, her, "vip")
    assert as_utc(user_of(db, her).vip_until) == membership_service.end_of_kst_day(open_at + timedelta(days=28))

    # 대화는 된다
    assert me.get("/api/v1/matches").status_code == 200
    assert me.post(f"/api/v1/matches/{match_id}/messages", json={"body": "점검 중에도 대화"}).status_code == 201

    # 기존 회원 사진 재검토는 막힌다
    r = me.post("/api/v1/me/photos", files={"file": ("me.jpg", b"x", "image/jpeg")})
    assert r.status_code == 409 and r.json()["detail"] == "MAINTENANCE"

    # 오픈 시각이 지나면 자동으로 열린다
    open_in(monkeypatch, paid_world, timedelta(seconds=-1))
    assert me.get("/api/v1/discover").status_code == 200
    assert me.get("/api/v1/me").json()["membership"]["before_open"] is False


def test_new_user_can_pay_and_submit_photo_during_maintenance(sent_codes, db, paid_world, monkeypatch):
    from tests.conftest import approve, choose_department, set_preferences, signup, upload_photo

    switch_on(monkeypatch, paid_world)
    open_in(monkeypatch, paid_world, timedelta(days=2))
    admin = admin_login(db)
    a = signup(sent_codes, db, "new@hufs.ac.kr")
    choose_department(a, db, "경영학부")
    set_preferences(a)
    # 첫 결제 안내가 점검 안내보다 먼저 (가입 단계를 먼저 끝내게)
    assert a.get("/api/v1/discover").json()["detail"] == "PAYMENT_REQUIRED"
    pay(admin, a)
    photo = upload_photo(a)  # 첫 사진은 점검 중에도 낼 수 있다
    approve(admin, photo)
    user = user_of(db, a)
    open_at = as_utc(paid_world.open_at)
    assert as_utc(user.member_until) == membership_service.end_of_kst_day(open_at + timedelta(days=28))
    assert a.get("/api/v1/discover").json()["detail"] == "MAINTENANCE"


def test_tester_can_use_matching_during_maintenance(sent_codes, db, paid_world, monkeypatch):
    admin = admin_login(db)
    monkeypatch.setattr(paid_world, "vip_test_emails", "wldns051205@hufs.ac.kr")
    switch_on(monkeypatch, paid_world)
    open_in(monkeypatch, paid_world, timedelta(days=2))
    vip = ready_user(sent_codes, db, admin, "wldns051205@hufs.ac.kr", gender="MALE", want="FEMALE")
    assert vip.get("/api/v1/discover").status_code == 200
