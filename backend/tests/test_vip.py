"""VIP 2주 이용권 (2026-10-03).

- 정가 6,000원, 오픈 할인 기간(VIP_DISCOUNT_UNTIL까지) 4,000원
- 결제는 가입비와 같은 직접 입금 (결제 코드 → "입금했어요" → 관리자 확인), 확인한 순간부터 14일
- VIP 중에는 다시 살 수 없고, 입금 확인 후에는 환불하지 않는다
- 혜택: LIKE 10개 / PASS 24시간 / 받은 LIKE 목록 / 사진 재검토 3일 / 남이 PASS하면 그날만 숨김
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import get_settings
from app.core.time import KST, kst_today, utcnow
from app.models import Like, PublicProfile, User
from app.models.payment import Payment
from tests.conftest import admin_login, discover_ids, ready_user

T = "2026-11-02"


def kst(day: str, hour=12):
    y, m, d = map(int, day.split("-"))
    return datetime(y, m, d, hour, tzinfo=KST).astimezone(timezone.utc)


@pytest.fixture
def vip_on(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "vip_enabled", True)
    monkeypatch.setattr(s, "vip_test_emails", "")  # 테스트 계정 없이 "돈 낸 VIP"만 본다
    monkeypatch.setattr(s, "payment_bank_name", "테스트은행")
    monkeypatch.setattr(s, "payment_account_number", "123-456-7890")
    monkeypatch.setattr(s, "payment_account_holder", "운영자")
    # 결제 가능 시간 판단·할인 날짜 판단에 쓰는 '지금'을 낮 12시로 고정
    monkeypatch.setattr("app.services.payment_service.utcnow", lambda: kst(T))
    return s


@pytest.fixture
def mails(monkeypatch):
    sent = []
    monkeypatch.setattr(
        "app.services.email_service.EmailService.send_admin_payment_request",
        staticmethod(lambda email, code, amount: sent.append((code, amount))),
    )
    return sent


def user_of(db, client) -> User:
    uid = db.query(PublicProfile).filter(PublicProfile.id == uuid.UUID(client.profile_id)).one().user_id
    return db.get(User, uid)


def make_vip(db, client, days=14):
    user = user_of(db, client)
    user.vip_until = utcnow() + timedelta(days=days)
    db.commit()


def buy_vip(admin, client):
    r = client.post("/api/v1/me/vip/request")
    assert r.status_code == 200, r.text
    pid = next(p for p in admin.get("/api/v1/admin/payments").json()["payments"] if p["kind"] == "VIP")["payment_id"]
    r = admin.post(f"/api/v1/admin/payments/{pid}/confirm")
    assert r.status_code == 200, r.text
    return pid


# ---------- 구매 ----------


def test_buy_vip_for_two_weeks(sent_codes, db, vip_on, mails):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")

    info = me.get("/api/v1/me/vip").json()
    assert info["visible"] is True and info["active"] is False and info["can_buy"] is True
    assert info["price"] == 6000 and info["regular_price"] == 6000 and info["discount_until"] is None
    assert info["days"] == 14
    pay = info["payment"]
    assert pay["amount"] == 6000 and len(pay["code"]) == 6 and pay["account_number"] == "123-456-7890"

    buy_vip(admin, me)
    assert mails == [(pay["code"], 6000)]
    info = me.get("/api/v1/me/vip").json()
    assert info["active"] is True and info["can_buy"] is False
    assert "끝난 뒤" in info["blocked_reason"]
    assert me.post("/api/v1/me/vip/request").status_code == 409  # VIP 중에는 다시 못 삼

    until = user_of(db, me).vip_until
    db.refresh(user_of(db, me))
    assert timedelta(days=13, hours=23) < until.replace(tzinfo=timezone.utc) - utcnow() <= timedelta(days=14)
    assert me.get("/api/v1/me").json()["vip"]["active"] is True


def test_open_discount_price(sent_codes, db, vip_on, monkeypatch):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    monkeypatch.setattr(vip_on, "vip_discount_until", kst_today())  # 오늘까지 할인
    info = me.get("/api/v1/me/vip").json()
    assert info["price"] == 4000 and info["regular_price"] == 6000 and info["discount_until"] == kst_today().isoformat()
    assert info["payment"]["amount"] == 4000

    # 할인이 끝난 뒤 다시 열면, 아직 "입금했어요"를 안 누른 코드는 정가로 바뀐다
    monkeypatch.setattr(vip_on, "vip_discount_until", kst_today() - timedelta(days=1))
    info = me.get("/api/v1/me/vip").json()
    assert info["price"] == 6000 and info["payment"]["amount"] == 6000 and info["discount_until"] is None


def test_price_is_kept_after_request(sent_codes, db, vip_on, monkeypatch):
    """할인 마지막 날 "입금했어요"를 누른 사람은 확인이 늦어져도 4,000원."""
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    monkeypatch.setattr(vip_on, "vip_discount_until", kst_today())
    me.post("/api/v1/me/vip/request")
    monkeypatch.setattr(vip_on, "vip_discount_until", kst_today() - timedelta(days=1))
    rows = admin.get("/api/v1/admin/payments").json()["payments"]
    assert [(p["kind"], p["amount"]) for p in rows] == [("VIP", 4000)]


def test_vip_not_for_sale_when_off(sent_codes, db, monkeypatch):
    monkeypatch.setattr(get_settings(), "vip_test_emails", "")
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    info = me.get("/api/v1/me/vip").json()
    assert info["visible"] is False and info["can_buy"] is False and info["payment"] is None
    assert me.post("/api/v1/me/vip/request").status_code == 409
    assert me.get("/api/v1/me").json()["vip"]["visible"] is False


def test_vip_needs_approved_photo(sent_codes, db, vip_on):
    from tests.conftest import choose_department, set_preferences, signup

    me = signup(sent_codes, db, "new@hufs.ac.kr")
    choose_department(me, db, "경영학부")
    set_preferences(me)
    info = me.get("/api/v1/me/vip").json()
    assert info["can_buy"] is False and "사진" in info["blocked_reason"]


def test_vip_payment_has_no_refund(sent_codes, db, vip_on):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    pid = buy_vip(admin, me)
    row = next(p for p in admin.get("/api/v1/admin/payments", params={"view": "history"}).json()["payments"] if p["payment_id"] == pid)
    assert row["kind"] == "VIP" and row["refundable"] is False
    assert admin.post(f"/api/v1/admin/payments/{pid}/refund").status_code == 409


def test_buy_again_after_expiry(sent_codes, db, vip_on):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    first = me.get("/api/v1/me/vip").json()["payment"]["code"]
    buy_vip(admin, me)
    user = user_of(db, me)
    user.vip_until = utcnow() - timedelta(minutes=1)  # 끝남
    db.commit()
    info = me.get("/api/v1/me/vip").json()
    assert info["active"] is False and info["can_buy"] is True
    assert info["payment"]["code"] != first  # 새 결제 코드


# ---------- 혜택이 VIP 기간에만 적용되는지 ----------


def test_benefits_end_when_vip_expires(sent_codes, db, vip_on):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    make_vip(db, me)
    assert me.get("/api/v1/discover").json()["daily_like_limit"] == 10
    assert me.get("/api/v1/me/photos").json()["resubmit"]["wait_days"] == 3

    user = user_of(db, me)
    user.vip_until = utcnow() - timedelta(seconds=1)
    db.commit()
    body = me.get("/api/v1/discover").json()
    assert body["daily_like_limit"] == 5 and body["vip"] is False
    assert me.get("/api/v1/me/photos").json()["resubmit"]["wait_days"] == 7
    assert me.get("/api/v1/liked-me").status_code == 403


def test_pass_on_paid_vip_hides_only_today(sent_codes, db, vip_on):
    admin = admin_login(db)
    vip = ready_user(sent_codes, db, admin, "vip@hufs.ac.kr", gender="MALE", want="FEMALE")
    make_vip(db, vip)
    her = ready_user(sent_codes, db, admin, "her@hufs.ac.kr", gender="FEMALE", want="MALE")
    her.post("/api/v1/passes", json={"profile_id": vip.profile_id})
    assert discover_ids(her) == []
    vip_id = user_of(db, vip).id
    for row in db.query(Like).filter(Like.to_user_id == vip_id):
        row.updated_at = row.updated_at - timedelta(days=1)
    db.commit()
    assert discover_ids(her) == [vip.profile_id]


# ---------- 받은 LIKE (혜택 3) ----------


def test_liked_me_list(sent_codes, db, vip_on):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr", gender="FEMALE", want="MALE")
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr", gender="FEMALE", want="MALE")
    c = ready_user(sent_codes, db, admin, "c@hufs.ac.kr", gender="FEMALE", want="MALE")
    blocked = ready_user(sent_codes, db, admin, "x@hufs.ac.kr", gender="FEMALE", want="MALE")
    for who in (a, b, c, blocked):
        assert who.post("/api/v1/likes", json={"profile_id": me.profile_id}).status_code == 200
    me.post("/api/v1/passes", json={"profile_id": b.profile_id})
    me.post("/api/v1/blocks", json={"profile_id": blocked.profile_id})

    # 무료 사용자에게는 아무것도 없다
    r = me.get("/api/v1/liked-me")
    assert r.status_code == 403 and r.json()["detail"] == "VIP_REQUIRED"

    make_vip(db, me)
    rows = me.get("/api/v1/liked-me").json()["profiles"]
    assert [p["profile_id"] for p in rows] == [c.profile_id, b.profile_id, a.profile_id]  # 최근 LIKE 순, 차단 제외
    assert [p["passed"] for p in rows] == [False, True, False]
    assert "photo" not in str(rows[0].keys()) and "tier" not in rows[0]

    # 목록에서 LIKE → 바로 매칭. PASS했던 사람에게도 LIKE할 수 있다. 하루 LIKE에 포함된다.
    r = me.post("/api/v1/likes", json={"profile_id": b.profile_id})
    assert r.status_code == 200, r.text
    assert r.json()["matched"] is True and r.json()["likes_left_today"] == 9
    rows = me.get("/api/v1/liked-me").json()["profiles"]
    assert b.profile_id not in [p["profile_id"] for p in rows]  # 매칭된 사람은 목록에서 빠짐


def test_liked_me_applies_matching_rules(sent_codes, db, vip_on):
    """추천 필수 조건(성별 등)에 맞지 않는 사람은 나를 LIKE했어도 목록에 없다."""
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    she = ready_user(sent_codes, db, admin, "she@hufs.ac.kr", gender="FEMALE", want="MALE")
    she.post("/api/v1/likes", json={"profile_id": me.profile_id})
    make_vip(db, me)
    # 그녀가 나중에 원하는 나이를 바꿔서 이제 나와 안 맞음
    she.put("/api/v1/me/preferences", json={"min_age": 30, "max_age": 35, "campus_mode": "ALL"})
    assert me.get("/api/v1/liked-me").json()["profiles"] == []


def test_boost_only_for_first_five_likes_of_the_day(sent_codes, db, vip_on, monkeypatch):
    """VIP가 하루 6번째 이후로 보낸 LIKE는 받는 사람의 추천 우대에 들어가지 않는다."""
    from app.services import profile_service

    admin = admin_login(db)
    vip = ready_user(sent_codes, db, admin, "vip@hufs.ac.kr", gender="MALE", want="FEMALE")
    make_vip(db, vip)
    women = [ready_user(sent_codes, db, admin, f"w{i}@hufs.ac.kr", gender="FEMALE", want="MALE") for i in range(7)]
    for w in women:
        assert vip.post("/api/v1/likes", json={"profile_id": w.profile_id}).status_code == 200
    vip_id = user_of(db, vip).id
    boosted = [vip_id in profile_service.liked_me_ids(db, user_of(db, w).id) for w in women]
    assert boosted == [True] * 5 + [False] * 2


# ---------- 화면 표시 ----------


def test_me_reports_vip(sent_codes, db, vip_on):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    v = me.get("/api/v1/me").json()["vip"]
    assert v == {"visible": True, "active": False, "until": None}
    make_vip(db, me)
    v = me.get("/api/v1/me").json()["vip"]
    assert v["active"] is True and v["until"] is not None
    detail = admin.get(f"/api/v1/admin/users/{user_of(db, me).id}").json()
    assert detail["vip_until"] is not None and detail["is_beta_member"] is True


def test_vip_settings_need_account(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "vip_enabled", True)
    monkeypatch.setattr(s, "payment_account_number", "")
    with pytest.raises(ValueError):
        s.validate_settings()
