"""유료 시작 시각 OPEN_AT (2026-10-04 점검 기간 → 2026-10-06 점검 기간 없앰).

- OPEN_AT 전에는 스위치가 켜져 있어도 베타처럼 모두 무료 (아무것도 막지 않음, 하루 LIKE 5개)
- 그 전에도 이용권·VIP를 미리 살 수 있다 → 기본 이용권은 오픈 시각부터 28일, VIP는 산 순간부터 바로 28일 (2026-10-06)
- OPEN_AT이 지나면 자동으로 유료: 이용권 없는 사람(베타 회원 포함)은 체험 이용자
- OPEN_AT이 없으면 스위치를 켠 순간부터 유료
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


def test_vip_before_open_starts_now_but_basic_part_from_open(maint, can_start):
    u = blank_user()
    membership_service.add_vip(None, u, kst(2026, 10, 8, 20))
    # VIP는 산 순간부터 28일 (2026-10-06: 바로 사용)
    assert as_utc(u.vip_until) == kst_midnight_after(2026, 11, 5)
    # 포함된 기본 이용권 몫은 유료 시작(10/10 18시)부터 28일 → VIP가 끝나도 이틀 남는다
    assert as_utc(u.member_until) == kst_midnight_after(2026, 11, 7)
    # 유료 시작 전에 기본을 하나 더 사면 뒤로 이어진다
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


def test_before_open_everything_is_free_and_presale_starts_at_open(sent_codes, db, paid_world, monkeypatch):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    her = ready_user(sent_codes, db, admin, "her@hufs.ac.kr", gender="FEMALE", want="MALE")
    other = ready_user(sent_codes, db, admin, "other@hufs.ac.kr", gender="FEMALE", want="MALE")
    switch_on(monkeypatch, paid_world, vip=True)
    open_in(monkeypatch, paid_world, timedelta(days=2))

    # 오픈 전: 베타처럼 무료 (점검 없음)
    r = me.get("/api/v1/discover")
    assert r.status_code == 200 and r.json()["like_access"] == "paid" and r.json()["daily_like_limit"] == 5
    assert me.post("/api/v1/passes", json={"profile_id": other.profile_id}).status_code == 200
    match_id = make_match(me, her)

    # 미리 살 수 있다 → 오픈 시각부터 28일
    pay(admin, me)
    open_at = as_utc(paid_world.open_at)
    assert as_utc(user_of(db, me).member_until) == membership_service.end_of_kst_day(open_at + timedelta(days=28))
    m = me.get("/api/v1/me").json()["membership"]
    assert m["before_open"] is True and m["open_at"] is not None
    # VIP는 유료 시작 전에 사도 바로 쓴다 (2026-10-06)
    pay(admin, her, "vip")
    assert her.get("/api/v1/me").json()["vip"]["active"] is True
    assert her.get("/api/v1/discover").json()["daily_like_limit"] == 10
    assert her.get("/api/v1/liked-me").status_code == 200
    assert me.post(f"/api/v1/matches/{match_id}/messages", json={"body": "안녕"}).status_code == 201

    # 오픈 시각이 지나면 자동으로 유료: 산 사람은 이용권, 안 산 사람(other)은 체험
    open_in(monkeypatch, paid_world, timedelta(seconds=-1))
    assert me.get("/api/v1/discover").json()["like_access"] == "paid"
    assert her.get("/api/v1/me").json()["vip"]["active"] is True
    r = other.get("/api/v1/discover")
    assert r.status_code == 200 and r.json()["like_access"] == "trial" and r.json()["likes_left_today"] == 3
    assert me.get("/api/v1/me").json()["membership"]["before_open"] is False


def test_no_payment_step_for_new_user_before_open(sent_codes, db, paid_world, monkeypatch):
    from tests.conftest import approve, choose_department, set_preferences, signup, upload_photo

    switch_on(monkeypatch, paid_world)
    open_in(monkeypatch, paid_world, timedelta(days=2))
    admin = admin_login(db)
    a = signup(sent_codes, db, "new@hufs.ac.kr")
    choose_department(a, db, "경영학부")
    set_preferences(a)
    assert a.get("/api/v1/discover").json()["detail"] == "PHOTO_REQUIRED"  # 결제 없이 바로 사진
    approve(admin, upload_photo(a))
    assert a.get("/api/v1/discover").status_code == 200


def test_tester_is_always_paid(sent_codes, db, paid_world, monkeypatch):
    admin = admin_login(db)
    monkeypatch.setattr(paid_world, "vip_test_emails", "wldns051205@hufs.ac.kr")
    switch_on(monkeypatch, paid_world)
    open_in(monkeypatch, paid_world, timedelta(seconds=-1))
    vip = ready_user(sent_codes, db, admin, "wldns051205@hufs.ac.kr", gender="MALE", want="FEMALE")
    assert vip.get("/api/v1/discover").json()["like_access"] == "paid"
