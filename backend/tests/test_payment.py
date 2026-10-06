"""이용권 직접 입금 (2026-10-03 가입비, 2026-10-04 구독제로 변경).

※ 2026-10-06 무료 체험부터는 가입 때 내지 않는다. 이 파일은 체험을 끈(FREE_TRIAL_LIKES=0) 예전 흐름과
  입금·확인·환불 자체를 확인한다. 체험 흐름은 test_free_trial.py.

흐름: 매칭 조건 → 결제 코드(CREATED) → "입금했어요"(REQUESTED) → 관리자 확인(CONFIRMED) → 사진 제출
첫 이용권 4주는 사진 검수 후 추천이 열리는 날부터 센다 (기간 계산은 test_membership.py).
"""

from datetime import datetime, timezone

import pytest

from app.core.config import get_settings
from app.core.time import KST
from app.models.payment import Payment
from app.models.user import User
from tests.conftest import (
    admin_login,
    approve,
    choose_department,
    set_preferences,
    signup,
    upload_photo,
)


def kst(hour, minute=0):
    return datetime(2026, 11, 2, hour, minute, tzinfo=KST).astimezone(timezone.utc)


@pytest.fixture
def clock(monkeypatch):
    """결제 가능 시간 판단에 쓰는 '지금' (기본: 한국 시간 낮 12시)."""
    now = {"value": kst(12)}
    monkeypatch.setattr("app.services.payment_service.utcnow", lambda: now["value"])
    return now


@pytest.fixture
def fee_on(monkeypatch, clock):
    s = get_settings()
    monkeypatch.setattr(s, "membership_enabled", True)
    monkeypatch.setattr(s, "vip_test_emails", "")
    monkeypatch.setattr(s, "payment_bank_name", "테스트은행")
    monkeypatch.setattr(s, "payment_account_number", "123-456-7890")
    monkeypatch.setattr(s, "payment_account_holder", "정지운")
    monkeypatch.setattr(s, "free_trial_likes", 0)
    monkeypatch.setattr(s, "membership_discount_until", datetime(2030, 1, 1, tzinfo=timezone.utc))
    return s


@pytest.fixture
def mails(monkeypatch):
    sent = []
    monkeypatch.setattr(
        "app.services.email_service.EmailService.send_admin_payment_request",
        staticmethod(lambda email, code, amount: sent.append((email, code, amount))),
    )
    return sent


def new_user(sent_codes, db, email, **kw):
    client = signup(sent_codes, db, email, **kw)
    choose_department(client, db, "경영학부")
    set_preferences(client)
    return client


def pending(admin):
    r = admin.get("/api/v1/admin/payments")
    assert r.status_code == 200, r.text
    return r.json()["payments"]


def history(admin):
    r = admin.get("/api/v1/admin/payments", params={"view": "history"})
    assert r.status_code == 200, r.text
    return r.json()["payments"]


# ---------- 스위치가 꺼져 있으면 지금과 똑같다 ----------


def test_fee_off_keeps_beta_flow(sent_codes, db):
    a = new_user(sent_codes, db, "off@hufs.ac.kr")
    me = a.get("/api/v1/me").json()["onboarding"]
    assert me["payment_required"] is False and me["pays_signup_fee"] is False
    assert a.get("/api/v1/me/payment").json() == {"required": False}
    upload_photo(a)  # 결제 없이 사진 제출
    user = db.query(User).filter(User.email == "off@hufs.ac.kr").one()
    assert user.is_beta_member is True


# ---------- 스위치를 켜면 ----------


def test_photo_blocked_until_confirmed(sent_codes, db, fee_on, mails):
    admin = admin_login(db)
    a = new_user(sent_codes, db, "pay@hufs.ac.kr", gender="MALE")
    me = a.get("/api/v1/me").json()["onboarding"]
    assert me["payment_required"] is True and me["pays_signup_fee"] is True

    # 사진 업로드·추천 모두 결제 전에는 막힘
    r = a.post("/api/v1/me/photos", files={"file": ("me.jpg", b"x", "image/jpeg")})
    assert r.status_code == 409 and r.json()["detail"] == "PAYMENT_REQUIRED"
    assert a.get("/api/v1/discover").json()["detail"] == "PAYMENT_REQUIRED"

    info = a.get("/api/v1/me/payment").json()
    assert info["required"] is True and info["status"] == "CREATED"
    assert info["amount"] == 3000  # 남녀 같음
    assert info["account_number"] == "123-456-7890"
    code = info["code"]
    assert len(code) == 6
    # 다시 열어도 같은 코드
    assert a.get("/api/v1/me/payment").json()["code"] == code

    # 결제 코드만 받은 사람은 관리자 목록에 안 나온다
    assert pending(admin) == []
    users = admin.get("/api/v1/admin/users").json()["users"]
    assert users[0]["onboarding_stage"] == "PAYMENT"

    r = a.post("/api/v1/me/payment/request")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "REQUESTED"
    # 관리자에게 알림 메일 (결제 코드·금액만)
    assert mails == [("super_admin@test.com", code, 3000)]
    # 두 번 눌러도 메일은 한 번
    a.post("/api/v1/me/payment/request")
    assert len(mails) == 1

    rows = pending(admin)
    assert [(p["code"], p["amount"]) for p in rows] == [(code, 3000)]
    assert "nickname" not in rows[0] and "email" not in rows[0]  # 익명성
    assert admin.get("/api/v1/admin/users").json()["users"][0]["onboarding_stage"] == "PAYMENT_CHECK"
    assert admin.get("/api/v1/admin/dashboard").json()["payments_pending"] == 1

    r = admin.post(f"/api/v1/admin/payments/{rows[0]['payment_id']}/confirm")
    assert r.status_code == 200, r.text
    assert pending(admin) == []
    body = a.get("/api/v1/me").json()
    me = body["onboarding"]
    assert me["payment_required"] is False and me["pays_signup_fee"] is True
    # 아직 시작 전: 사진 검수가 끝나 추천이 열리는 날부터 28일 (D1)
    assert body["membership"]["status"] == "banked" and body["membership"]["banked_days"] == 28
    assert body["membership"]["until"] is None
    # 연장용으로 다시 열면 새 코드 (가입 단계는 끝남)
    again = a.get("/api/v1/me/payment").json()
    assert again["required"] is False and again["code"] != code
    upload_photo(a)  # 이제 사진 제출 가능
    assert admin.get("/api/v1/admin/users").json()["users"][0]["onboarding_stage"] == "REVIEW"


def test_female_pays_same_amount(sent_codes, db, fee_on):
    a = new_user(sent_codes, db, "f@hufs.ac.kr", gender="FEMALE")
    assert a.get("/api/v1/me/payment").json()["amount"] == 3000


def test_payment_needs_profile_and_preferences_first(sent_codes, db, fee_on):
    a = signup(sent_codes, db, "early@hufs.ac.kr")
    assert a.get("/api/v1/me/payment").json()["detail"] == "PROFILE_REQUIRED"
    choose_department(a, db, "경영학부")
    assert a.get("/api/v1/me/payment").json()["detail"] == "PREFERENCES_REQUIRED"
    assert a.post("/api/v1/me/payment/request").status_code == 409


def test_beta_member_also_pays(sent_codes, db, fee_on):
    """2026-10-04 구독제: 베타 회원도 면제가 아니다."""
    a = new_user(sent_codes, db, "beta@hufs.ac.kr")
    user = db.query(User).filter(User.email == "beta@hufs.ac.kr").one()
    assert user.is_beta_member is False  # 스위치를 켠 뒤 가입 → 기록상 일반 회원
    user.is_beta_member = True  # 베타 기간에 가입한 사람이라고 가정
    db.commit()
    assert a.get("/api/v1/me").json()["onboarding"]["payment_required"] is True
    r = a.post("/api/v1/me/photos", files={"file": ("me.jpg", b"x", "image/jpeg")})
    assert r.status_code == 409 and r.json()["detail"] == "PAYMENT_REQUIRED"


# ---------- 결제 가능 시간 (오전 6시 ~ 밤 12시) ----------


def test_closed_at_night(sent_codes, db, fee_on, clock, mails):
    a = new_user(sent_codes, db, "night@hufs.ac.kr")
    clock["value"] = kst(2)
    info = a.get("/api/v1/me/payment").json()
    assert info["open_now"] is False
    assert info["account_number"] is None  # 밤에는 계좌번호를 숨김
    r = a.post("/api/v1/me/payment/request")
    assert r.status_code == 409 and "운영 시간 외" in r.json()["detail"]
    assert mails == []

    clock["value"] = kst(5, 59)
    assert a.post("/api/v1/me/payment/request").status_code == 409
    clock["value"] = kst(6)
    assert a.post("/api/v1/me/payment/request").status_code == 200


def test_just_before_midnight_is_open(sent_codes, db, fee_on, clock):
    a = new_user(sent_codes, db, "late@hufs.ac.kr")
    clock["value"] = kst(23, 59)
    assert a.post("/api/v1/me/payment/request").status_code == 200
    # 밤 12시가 지나도 이미 요청한 사람은 계좌·대기 상태가 그대로 보인다
    clock["value"] = kst(0, 30)
    info = a.get("/api/v1/me/payment").json()
    assert info["status"] == "REQUESTED" and info["account_number"] == "123-456-7890"


# ---------- 입금 없음 / 환불 ----------


def test_reject_then_request_again(sent_codes, db, fee_on, mails):
    admin = admin_login(db)
    a = new_user(sent_codes, db, "rej@hufs.ac.kr")
    a.post("/api/v1/me/payment/request")
    pid = pending(admin)[0]["payment_id"]
    assert admin.post(f"/api/v1/admin/payments/{pid}/reject").status_code == 200
    assert a.get("/api/v1/me/payment").json()["status"] == "REJECTED"
    assert a.post("/api/v1/me/photos", files={"file": ("me.jpg", b"x", "image/jpeg")}).status_code == 409

    # 같은 코드로 다시 요청 → 메일 다시 감
    assert a.post("/api/v1/me/payment/request").json()["status"] == "REQUESTED"
    assert len(mails) == 2
    assert pending(admin)[0]["payment_id"] == pid


def test_refund_only_before_review(sent_codes, db, fee_on):
    admin = admin_login(db)
    a = new_user(sent_codes, db, "refund@hufs.ac.kr")
    a.post("/api/v1/me/payment/request")
    pid = pending(admin)[0]["payment_id"]
    admin.post(f"/api/v1/admin/payments/{pid}/confirm")

    # 사진을 냈지만 아직 검수 전 → 환불 가능, 사진은 대기열에서 빠짐
    upload_photo(a)
    assert history(admin)[0]["refundable"] is True
    r = admin.post(f"/api/v1/admin/payments/{pid}/refund")
    assert r.status_code == 200, r.text
    assert admin.get("/api/v1/admin/dashboard").json()["photos_pending"] == 0
    assert a.get("/api/v1/me").json()["onboarding"]["payment_required"] is True
    assert a.post("/api/v1/me/photos", files={"file": ("me.jpg", b"x", "image/jpeg")}).status_code == 409
    # 다시 결제하면 새 코드
    old_code = db.get(Payment, __import__("uuid").UUID(pid)).code
    assert a.get("/api/v1/me/payment").json()["code"] != old_code


def test_no_refund_after_review_even_if_rejected(sent_codes, db, fee_on):
    admin = admin_login(db)
    a = new_user(sent_codes, db, "noref@hufs.ac.kr")
    a.post("/api/v1/me/payment/request")
    pid = pending(admin)[0]["payment_id"]
    admin.post(f"/api/v1/admin/payments/{pid}/confirm")
    photo = upload_photo(a)
    r = admin.put(
        f"/api/v1/admin/photo-reviews/{photo}/evaluation",
        json={"decision": "REJECTED", "reject_reason": "얼굴이 잘 보이지 않아요"},
    )
    assert r.status_code == 200, r.text
    assert history(admin)[0]["refundable"] is False
    r = admin.post(f"/api/v1/admin/payments/{pid}/refund")
    assert r.status_code == 409


def test_approved_user_can_discover_after_payment(sent_codes, db, fee_on):
    admin = admin_login(db)
    a = new_user(sent_codes, db, "full@hufs.ac.kr")
    a.post("/api/v1/me/payment/request")
    admin.post(f"/api/v1/admin/payments/{pending(admin)[0]['payment_id']}/confirm")
    approve(admin, upload_photo(a))
    assert a.get("/api/v1/discover").status_code == 200
    m = a.get("/api/v1/me").json()["membership"]
    assert m["status"] == "active" and m["banked_days"] == 0 and 28 <= m["days_left"] <= 29
    # 이용권이 시작되면 환불할 수 없다
    assert history(admin)[0]["refundable"] is False


# ---------- 권한 ----------


def test_only_super_admin_sees_payments(sent_codes, db, fee_on):
    a = new_user(sent_codes, db, "perm@hufs.ac.kr")
    a.post("/api/v1/me/payment/request")
    for role in ("MODERATOR", "PHOTO_REVIEWER"):
        other = admin_login(db, role=role)
        assert other.get("/api/v1/admin/payments").status_code == 403
    super_admin = admin_login(db)
    pid = pending(super_admin)[0]["payment_id"]
    moderator = admin_login(db, role="MODERATOR", email="mod2@test.com")
    assert moderator.post(f"/api/v1/admin/payments/{pid}/confirm").status_code == 403


def test_user_cannot_confirm_own_payment(sent_codes, db, fee_on):
    a = new_user(sent_codes, db, "self@hufs.ac.kr")
    a.post("/api/v1/me/payment/request")
    pid = str(db.query(Payment).one().id)
    assert a.post(f"/api/v1/admin/payments/{pid}/confirm").status_code in (401, 403)


def test_codes_are_unique(sent_codes, db, fee_on):
    codes = {new_user(sent_codes, db, f"u{i}@hufs.ac.kr").get("/api/v1/me/payment").json()["code"] for i in range(5)}
    assert len(codes) == 5


def test_fee_on_requires_account_settings(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "membership_enabled", True)
    monkeypatch.setattr(s, "payment_account_number", "")
    with pytest.raises(ValueError):
        s.validate_settings()


def test_payment_from_match_suspended_user_is_flagged_for_admin(sent_codes, db, fee_on, mails):
    """매칭 정지 중인 사람의 결제 (2026-10-05): 관리자 입금 확인 목록에만 경고가 뜨고, 사용자 화면은 그대로다."""
    admin = admin_login(db)
    a = new_user(sent_codes, db, "a@hufs.ac.kr")
    b = new_user(sent_codes, db, "b@hufs.ac.kr")
    a_info_before = a.get("/api/v1/me/payment").json()
    user_a = db.query(User).filter(User.email == "a@hufs.ac.kr").one()
    r = admin.patch(f"/api/v1/admin/users/{user_a.id}/match-suspension", json={"suspended": True, "reason": "테스트 사유"})
    assert r.status_code == 200, r.text

    # 사용자 화면: 정지 전과 똑같다
    a_info = a.get("/api/v1/me/payment").json()
    assert a_info == a_info_before and "match_suspended" not in a.get("/api/v1/me/payment").text
    a.post("/api/v1/me/payment/request")
    b.post("/api/v1/me/payment/request")

    rows = {p["code"]: p for p in pending(admin)}
    flagged = rows[a_info["code"]]
    assert flagged["match_suspended"] is True and flagged["user_id"] == str(user_a.id)
    normal = rows[b.get("/api/v1/me/payment").json()["code"]]
    assert normal["match_suspended"] is False and normal["user_id"] is None

    # 경고만 할 뿐, 관리자가 확인하면 그대로 처리된다
    assert admin.post(f"/api/v1/admin/payments/{flagged['payment_id']}/confirm").status_code == 200
    history = admin.get("/api/v1/admin/payments?view=history").json()["payments"]
    assert history[0]["match_suspended"] is True
