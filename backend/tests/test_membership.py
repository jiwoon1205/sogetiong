"""이용권 구독제 (2026-10-04, `유료화(구독제) 코드 구현 가이드라인` 0장 D1~D10).

- 기본 4주(28일) 3,000원, VIP 4주 6,000원 = 기본 포함. 끝나는 시각은 그날 밤 12시(한국 시간)로 올림
- 첫 이용권은 추천이 열리는 날(승인 사진 + 등급)부터 (D1). 언제든 연장 (D2)
- VIP를 사면 남은 기본 기간은 VIP 뒤로 밀린다
- 이용권이 없으면 추천·LIKE·PASS·받은 LIKE·사진 재검토만 막고 대화는 된다. 끝난 사람은 남의 추천에 안 나온다 (D5)
- 베타 회원도 유료 (D7), 관리자 기간 조정 (D8), 테스트 계정은 항상 이용 (D10)
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import get_settings
from app.core.time import KST, as_utc, utcnow
from app.models import AuditLog, Notification, PublicProfile, User
from app.services import membership_service
from tests.conftest import admin_login, discover_ids, ready_user


def kst(y, m, d, hour=12, minute=0):
    return datetime(y, m, d, hour, minute, tzinfo=KST).astimezone(timezone.utc)


def kst_midnight_after(y, m, d):
    """y-m-d 날의 밤 12시 (= 다음 날 0시, 한국 시간)"""
    return datetime(y, m, d, tzinfo=KST).astimezone(timezone.utc) + timedelta(days=1)


# ---------- 날짜 계산 (DB 없이) ----------


@pytest.fixture
def on(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "membership_enabled", True)
    monkeypatch.setattr(s, "vip_test_emails", "")
    return s


@pytest.fixture
def can_start(monkeypatch):
    """추천이 열린 상태(승인 사진 + 등급)인지 직접 정한다."""
    state = {"value": True}
    monkeypatch.setattr(membership_service, "can_start", lambda db, user: state["value"])
    return state


def blank_user(**kw) -> User:
    return User(email="x@hufs.ac.kr", member_days_banked=0, **kw)


def test_end_of_kst_day():
    assert membership_service.end_of_kst_day(kst(2026, 10, 1, 15)) == kst_midnight_after(2026, 10, 1)
    # 한국 시간 새벽 1시도 그날 밤 12시
    assert membership_service.end_of_kst_day(kst(2026, 10, 1, 1)) == kst_midnight_after(2026, 10, 1)
    # 정확히 밤 12시면 그대로 (하루가 더 붙지 않음)
    midnight = kst_midnight_after(2026, 10, 1)
    assert membership_service.end_of_kst_day(midnight) == midnight


def test_first_purchase_after_review_starts_now(on, can_start):
    u = blank_user()
    membership_service.add_membership(None, u, kst(2026, 10, 1))
    # 10/1 낮 + 28일 = 10/29 낮 → 10/29 밤 12시
    assert as_utc(u.member_until) == kst_midnight_after(2026, 10, 29)
    assert u.member_days_banked == 0


def test_first_purchase_before_review_is_banked(on, can_start):
    can_start["value"] = False
    u = blank_user()
    membership_service.add_membership(None, u, kst(2026, 10, 1))
    assert u.member_until is None and u.member_days_banked == 28
    assert membership_service.status(u, kst(2026, 10, 1)) == "banked"
    # 사진이 승인돼 등급이 정해진 날(10/5)부터 28일
    can_start["value"] = True
    assert membership_service.start_banked(None, u, kst(2026, 10, 5)) is True
    assert as_utc(u.member_until) == kst_midnight_after(2026, 11, 2)
    assert u.member_days_banked == 0
    assert membership_service.start_banked(None, u, kst(2026, 10, 6)) is False  # 두 번 시작하지 않음


def test_two_purchases_before_review_add_up(on, can_start):
    can_start["value"] = False
    u = blank_user()
    membership_service.add_membership(None, u, kst(2026, 10, 1))
    membership_service.add_membership(None, u, kst(2026, 10, 2))
    assert u.member_days_banked == 56


def test_renew_early_adds_after_end(on, can_start):
    u = blank_user(member_until=kst_midnight_after(2026, 10, 29))
    membership_service.add_membership(None, u, kst(2026, 10, 20))
    # 남은 기간 뒤에 정확히 28일 (밤 12시 + 28일 = 밤 12시)
    assert as_utc(u.member_until) == kst_midnight_after(2026, 11, 26)


def test_renew_after_expiry_starts_today(on, can_start):
    u = blank_user(member_until=kst_midnight_after(2026, 10, 29))
    membership_service.add_membership(None, u, kst(2026, 11, 3))
    assert as_utc(u.member_until) == kst_midnight_after(2026, 12, 1)


def test_vip_pushes_remaining_basic_back(on):
    """구독제 설계 예시: 10/1 기본 → 10/19 VIP (기본 10일 남음) → VIP ~11/16, 기본 ~11/26"""
    u = blank_user(member_until=kst_midnight_after(2026, 10, 29))
    membership_service.add_vip(None, u, kst(2026, 10, 19))
    assert as_utc(u.vip_until) == kst_midnight_after(2026, 11, 16)
    assert as_utc(u.member_until) == kst_midnight_after(2026, 11, 26)


def test_vip_without_basic_ends_same_day(on):
    u = blank_user()
    membership_service.add_vip(None, u, kst(2026, 10, 19))
    assert as_utc(u.vip_until) == as_utc(u.member_until) == kst_midnight_after(2026, 11, 16)


def test_basic_during_vip_adds_to_basic_only(on, can_start):
    u = blank_user()
    membership_service.add_vip(None, u, kst(2026, 10, 19))
    membership_service.add_membership(None, u, kst(2026, 10, 25))
    assert as_utc(u.vip_until) == kst_midnight_after(2026, 11, 16)
    assert as_utc(u.member_until) == kst_midnight_after(2026, 12, 14)


def test_has_membership_and_days_left(on):
    end = kst_midnight_after(2026, 10, 29)
    u = blank_user(member_until=end)
    assert membership_service.has_membership(u, kst(2026, 10, 29, 23, 59)) is True
    assert membership_service.has_membership(u, end) is False
    assert membership_service.days_left(u, kst(2026, 10, 27, 12)) == 3  # 2.5일 → 3
    assert membership_service.days_left(u, end) is None
    assert membership_service.status(u, end) == "expired"
    assert membership_service.status(blank_user(), end) == "none"


def test_switch_off_means_everyone_has_membership(monkeypatch):
    monkeypatch.setattr(get_settings(), "membership_enabled", False)
    u = blank_user()
    assert membership_service.has_membership(u) is True
    assert membership_service.needs_first_payment(u, has_approved_photo=False) is False


def test_tester_always_has_membership(on, monkeypatch):
    monkeypatch.setattr(on, "vip_test_emails", "x@hufs.ac.kr")
    u = blank_user()
    assert membership_service.has_membership(u) is True
    assert membership_service.needs_first_payment(u, has_approved_photo=False) is False


def test_adjust(on):
    end = kst_midnight_after(2026, 10, 29)
    u = blank_user(member_until=end)
    membership_service.adjust(u, 7, kst(2026, 10, 20))
    assert as_utc(u.member_until) == end + timedelta(days=7)
    membership_service.adjust(u, -7, kst(2026, 10, 20))
    assert as_utc(u.member_until) == end
    # 끝난 사람: 더하기는 지금부터, 빼기는 무시
    gone = blank_user(member_until=end)
    membership_service.adjust(gone, -3, kst(2026, 11, 5))
    assert as_utc(gone.member_until) == end
    membership_service.adjust(gone, 3, kst(2026, 11, 5))
    assert as_utc(gone.member_until) == kst_midnight_after(2026, 11, 8)


def test_vip_requires_membership_switch(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "vip_enabled", True)
    monkeypatch.setattr(s, "membership_enabled", False)
    monkeypatch.setattr(s, "payment_bank_name", "은행")
    monkeypatch.setattr(s, "payment_account_number", "1")
    monkeypatch.setattr(s, "payment_account_holder", "운영자")
    with pytest.raises(ValueError):
        s.validate_settings()
    monkeypatch.setattr(s, "membership_enabled", True)
    s.validate_settings()


# ---------- API (베타 회원 = 스위치를 켜기 전에 가입·승인된 사람) ----------


@pytest.fixture
def paid_world(monkeypatch):
    """결제 계좌·결제 가능 시간(낮 12시)을 준비한다. 스위치는 테스트에서 켠다."""
    s = get_settings()
    monkeypatch.setattr(s, "vip_test_emails", "")
    monkeypatch.setattr(s, "payment_bank_name", "테스트은행")
    monkeypatch.setattr(s, "payment_account_number", "123-456-7890")
    monkeypatch.setattr(s, "payment_account_holder", "운영자")
    monkeypatch.setattr("app.services.payment_service.utcnow", lambda: kst(2026, 11, 2))
    monkeypatch.setattr(
        "app.services.email_service.EmailService.send_admin_payment_request",
        staticmethod(lambda email, code, amount: None),
    )
    return s


def switch_on(monkeypatch, s, vip=False):
    monkeypatch.setattr(s, "membership_enabled", True)
    monkeypatch.setattr(s, "vip_enabled", vip)


def user_of(db, client) -> User:
    uid = db.query(PublicProfile).filter(PublicProfile.id == uuid.UUID(client.profile_id)).one().user_id
    user = db.get(User, uid)
    db.refresh(user)
    return user


def pay(admin, client, kind="basic"):
    url = "/api/v1/me/payment/request" if kind == "basic" else "/api/v1/me/vip/request"
    r = client.post(url)
    assert r.status_code == 200, r.text
    want = "SIGNUP" if kind == "basic" else "VIP"
    pid = next(p for p in admin.get("/api/v1/admin/payments").json()["payments"] if p["kind"] == want)["payment_id"]
    r = admin.post(f"/api/v1/admin/payments/{pid}/confirm")
    assert r.status_code == 200, r.text
    return pid


def make_match(a, b):
    assert a.post("/api/v1/likes", json={"profile_id": b.profile_id}).status_code == 200
    r = b.post("/api/v1/likes", json={"profile_id": a.profile_id})
    assert r.status_code == 200 and r.json()["matched"] is True, r.text
    return r.json()["match_id"]


def test_beta_member_must_buy_after_switch(sent_codes, db, paid_world, monkeypatch):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    her = ready_user(sent_codes, db, admin, "her@hufs.ac.kr", gender="FEMALE", want="MALE")
    match_id = make_match(me, her)
    switch_on(monkeypatch, paid_world)

    body = me.get("/api/v1/me").json()
    assert body["onboarding"]["payment_required"] is False  # 가입 단계가 아니라 "이용권이 끝났어요" 화면
    assert body["membership"]["active"] is False and body["membership"]["status"] == "none"
    for r in (
        me.get("/api/v1/discover"),
        me.post("/api/v1/passes", json={"profile_id": her.profile_id}),
        me.post("/api/v1/likes", json={"profile_id": her.profile_id}),
    ):
        assert r.status_code == 409 and r.json()["detail"] == "MEMBERSHIP_REQUIRED", r.text
    # 대화는 이용권 없이도 된다
    assert me.get("/api/v1/matches").status_code == 200
    r = me.post(f"/api/v1/matches/{match_id}/messages", json={"body": "안녕하세요"})
    assert r.status_code == 201, r.text
    assert me.get(f"/api/v1/matches/{match_id}/messages").status_code == 200

    # 사진 재검토도 막힌다 (D9)
    r = me.post("/api/v1/me/photos", files={"file": ("me.jpg", b"x", "image/jpeg")})
    assert r.status_code == 409 and r.json()["detail"] == "MEMBERSHIP_REQUIRED"

    # 연장 화면에서 3,000원 → 바로 시작 (이미 승인·등급 있음)
    info = me.get("/api/v1/me/payment").json()
    assert info["required"] is False and info["amount"] == 3000
    pay(admin, me)
    m = me.get("/api/v1/me").json()["membership"]
    assert m["status"] == "active" and 28 <= m["days_left"] <= 29
    assert as_utc(user_of(db, me).member_until).astimezone(KST).hour == 0
    assert me.get("/api/v1/discover").status_code == 200


def test_expired_people_are_hidden_but_kept_in_liked_list(sent_codes, db, paid_world, monkeypatch):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    paid = ready_user(sent_codes, db, admin, "paid@hufs.ac.kr", gender="FEMALE", want="MALE")
    gone = ready_user(sent_codes, db, admin, "gone@hufs.ac.kr", gender="FEMALE", want="MALE")
    assert gone.post("/api/v1/likes", json={"profile_id": me.profile_id}).status_code == 200  # 끝나기 전에 보낸 LIKE
    switch_on(monkeypatch, paid_world, vip=True)
    pay(admin, paid)
    pay(admin, me, "vip")

    # 이용권 없는 사람(gone)은 추천에 안 나온다
    assert discover_ids(me) == [paid.profile_id]
    # 하지만 나를 LIKE한 사람 목록에는 나오고, LIKE하면 바로 매칭 → 대화
    rows = me.get("/api/v1/liked-me").json()["profiles"]
    assert [p["profile_id"] for p in rows] == [gone.profile_id]
    r = me.post("/api/v1/likes", json={"profile_id": gone.profile_id})
    assert r.status_code == 200 and r.json()["matched"] is True
    r = gone.post(f"/api/v1/matches/{r.json()['match_id']}/messages", json={"body": "반가워요"})
    assert r.status_code == 201, r.text


def test_vip_purchase_pushes_basic_back(sent_codes, db, paid_world, monkeypatch):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    switch_on(monkeypatch, paid_world, vip=True)
    pay(admin, me)
    basic_end = as_utc(user_of(db, me).member_until)
    info = me.get("/api/v1/me/vip").json()
    assert info["can_buy"] is True and info["price"] == 6000 and 28 <= info["member_days_left"] <= 29
    pay(admin, me, "vip")
    user = user_of(db, me)
    assert as_utc(user.member_until) == basic_end + timedelta(days=28)
    assert as_utc(user.vip_until) <= basic_end + timedelta(days=1)  # VIP는 오늘부터 28일
    assert me.get("/api/v1/discover").json()["daily_like_limit"] == 10


def test_vip_can_be_bought_without_basic(sent_codes, db, paid_world, monkeypatch):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    switch_on(monkeypatch, paid_world, vip=True)
    assert me.get("/api/v1/discover").status_code == 409
    pay(admin, me, "vip")
    user = user_of(db, me)
    assert as_utc(user.vip_until) == as_utc(user.member_until)
    assert me.get("/api/v1/discover").status_code == 200


def test_renewal_is_not_refundable(sent_codes, db, paid_world, monkeypatch):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    switch_on(monkeypatch, paid_world)
    pid = pay(admin, me)
    row = next(p for p in admin.get("/api/v1/admin/payments", params={"view": "history"}).json()["payments"] if p["payment_id"] == pid)
    assert row["refundable"] is False
    assert admin.post(f"/api/v1/admin/payments/{pid}/refund").status_code == 409


def test_new_user_full_flow_and_start_notice(sent_codes, db, paid_world, monkeypatch):
    from tests.conftest import approve, choose_department, set_preferences, signup, upload_photo

    switch_on(monkeypatch, paid_world)
    admin = admin_login(db)
    a = signup(sent_codes, db, "new@hufs.ac.kr")
    choose_department(a, db, "경영학부")
    set_preferences(a)
    assert a.get("/api/v1/me").json()["onboarding"]["payment_required"] is True
    assert a.get("/api/v1/me/payment").json()["required"] is True
    pay(admin, a)
    user = user_of(db, a)
    assert user.member_until is None and user.member_days_banked == 28
    photo = upload_photo(a)
    assert a.get("/api/v1/discover").json()["detail"] == "PHOTO_APPROVAL_REQUIRED"  # 검수 중에는 "평가 중"이 먼저
    approve(admin, photo)
    user = user_of(db, a)
    assert user.member_days_banked == 0
    assert 28 <= membership_service.days_left(user) <= 29
    assert db.query(Notification).filter(Notification.user_id == user.id, Notification.type == "MEMBERSHIP_STARTED").count() == 1
    assert a.get("/api/v1/discover").status_code == 200


def test_tier_change_starts_banked_days(sent_codes, db, paid_world, monkeypatch):
    """등급 없는 예전 평가만 있던 사람: 관리자가 등급을 정하는 순간 쌓아 둔 일수가 시작된다."""
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    switch_on(monkeypatch, paid_world)
    user = user_of(db, me)
    user.member_days_banked = 28
    db.commit()
    r = admin.patch(f"/api/v1/admin/users/{user.id}/appearance-tier", json={"tier": "HIGH", "reason": "등급 다시 정함"})
    assert r.status_code == 200, r.text
    user = user_of(db, me)
    assert user.member_days_banked == 0 and user.member_until is not None


def test_admin_adjust(sent_codes, db, paid_world, monkeypatch):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    switch_on(monkeypatch, paid_world)
    uid = user_of(db, me).id
    url = f"/api/v1/admin/users/{uid}/membership-adjust"
    r = admin.post(url, json={"days": 7, "reason": "입금 확인 지연 보상"})
    assert r.status_code == 200, r.text
    assert r.json()["membership_status"] == "active"
    first = as_utc(user_of(db, me).member_until)
    admin.post(url, json={"days": -2, "reason": "실수 정정"})
    assert as_utc(user_of(db, me).member_until) == first - timedelta(days=2)
    logs = db.query(AuditLog).filter(AuditLog.action == "MEMBERSHIP_ADJUST").count()
    assert logs == 2
    assert admin.post(url, json={"days": 0, "reason": "없음"}).status_code == 400
    assert admin.post(url, json={"days": 61, "reason": "너무 많음"}).status_code == 422
    moderator = admin_login(db, role="MODERATOR", email="mod@test.com")
    assert moderator.post(url, json={"days": 1, "reason": "권한 없음"}).status_code == 403
    detail = admin.get(f"/api/v1/admin/users/{uid}").json()
    assert detail["membership_status"] == "active" and detail["member_days_banked"] == 0
    dash = admin.get("/api/v1/admin/dashboard").json()
    assert dash["members_active"] == 1 and dash["members_expiring_week"] == 1 and dash["members_vip"] == 0


def test_tester_account_never_pays(sent_codes, db, paid_world, monkeypatch):
    admin = admin_login(db)
    monkeypatch.setattr(paid_world, "vip_test_emails", "wldns051205@hufs.ac.kr")
    her = ready_user(sent_codes, db, admin, "her@hufs.ac.kr", gender="FEMALE", want="MALE")
    switch_on(monkeypatch, paid_world)
    # 테스트 계정은 스위치를 켠 뒤에 가입해도 결제 없이 사진을 낼 수 있다
    vip = ready_user(sent_codes, db, admin, "wldns051205@hufs.ac.kr", gender="MALE", want="FEMALE")
    assert vip.get("/api/v1/discover").status_code == 200
    assert vip.get("/api/v1/me/payment").json() == {"required": False}
    assert vip.get("/api/v1/me").json()["membership"]["free"] is True
    # 테스트 계정은 남의 추천에도 나온다 (D10). her는 이용권이 있어야 추천을 본다.
    pay(admin, her)
    assert discover_ids(her) == [vip.profile_id]


def test_expiry_is_checked_live(sent_codes, db, paid_world, monkeypatch):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    switch_on(monkeypatch, paid_world)
    pay(admin, me)
    assert me.get("/api/v1/discover").status_code == 200
    user = user_of(db, me)
    user.member_until = utcnow() - timedelta(seconds=1)
    db.commit()
    r = me.get("/api/v1/discover")
    assert r.status_code == 409 and r.json()["detail"] == "MEMBERSHIP_REQUIRED"
    assert me.get("/api/v1/me").json()["membership"]["status"] == "expired"
