"""탈퇴 후 재가입하면 예전 계정의 것을 이어받는다 (2026-10-05).

- 외모 점수·등급·사진 승인 → 사진 단계 없이 바로 추천
- 재검토 대기(마지막 평가 후 7일)와 "바로 재검토 평생 1번" 사용 여부
- 남은 이용권·VIP 기간 (한 번만 이어받음)
- 매칭 정지
"""

from datetime import timedelta

from app.core.config import get_settings
from app.core.time import as_utc, utcnow
from app.models.user import User

from tests.conftest import (
    admin_login,
    approve,
    choose_department,
    discover_ids,
    jpeg_with_exif,
    ready_user,
    set_preferences,
    signup,
    upload_photo,
)

EMAIL = "a@hufs.ac.kr"


def _delete(client):
    assert client.delete("/api/v1/me", json={"password": "goodpass123"}).status_code == 200


def _rejoin(sent_codes, db, **kw):
    client = signup(sent_codes, db, EMAIL, **kw)
    choose_department(client, db, "경영학부")
    set_preferences(client)
    return client


def _user(db, email=EMAIL) -> User:
    db.expire_all()
    return db.query(User).filter(User.email == email).one()


def test_scores_tier_and_photo_carry_over(sent_codes, db):
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, EMAIL, gender="FEMALE", prefs={"preferred_gender": "MALE"})
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr", gender="MALE", prefs={"preferred_gender": "FEMALE"})
    before = a.get("/api/v1/me/profile").json()
    _delete(a)

    a2 = _rejoin(sent_codes, db, gender="FEMALE", want="MALE")
    me = a2.get("/api/v1/me").json()
    assert me["onboarding"]["photo_approved"] is True  # 사진 다시 안 내도 됨
    after = a2.get("/api/v1/me/profile").json()
    assert before["appearance"] is not None
    assert after["appearance"] == before["appearance"]  # 점수 그대로
    # 등급도 이어져서 바로 추천을 주고받는다
    assert b.profile_id in discover_ids(a2)
    assert a2.profile_id in discover_ids(b)


def test_resubmit_wait_carries_over(sent_codes, db):
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, EMAIL)
    # 바로 재검토(평생 1번)를 써서 승인까지 받음
    approve(admin, upload_photo(a))
    _delete(a)

    a2 = _rejoin(sent_codes, db)
    assert a2.get("/api/v1/me/photos").json()["resubmit"]["allowed"] is False
    r = a2.post("/api/v1/me/photos", files={"file": ("me.jpg", jpeg_with_exif(), "image/jpeg")})
    assert r.status_code == 429, r.text  # 7일이 안 지났고 바로 재검토도 이미 씀 → 새 계정에서도 못 냄


def test_free_rereview_still_left_if_unused(sent_codes, db):
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, EMAIL)
    _delete(a)
    a2 = _rejoin(sent_codes, db)
    # 평가 직후라 7일 대기 중이지만, 바로 재검토 1번은 아직 남아 있다 (예전 계정 그대로)
    r = a2.post("/api/v1/me/photos", files={"file": ("me.jpg", jpeg_with_exif(), "image/jpeg")})
    assert r.status_code == 201, r.text


def test_membership_and_vip_carry_over_once(sent_codes, db):
    a = signup(sent_codes, db, EMAIL)
    user = _user(db)
    until = utcnow() + timedelta(days=20)
    vip = utcnow() + timedelta(days=10)
    user.member_until, user.vip_until = until, vip
    db.commit()
    _delete(a)

    a2 = signup(sent_codes, db, EMAIL)
    new = _user(db)
    assert abs((as_utc(new.member_until) - until).total_seconds()) < 1
    assert abs((as_utc(new.vip_until) - vip).total_seconds()) < 1

    # 또 탈퇴·재가입해도 기간이 두 배가 되지 않는다
    _delete(a2)
    signup(sent_codes, db, EMAIL)
    third = _user(db)
    assert abs((as_utc(third.member_until) - until).total_seconds()) < 1
    olds = db.query(User).filter(User.status == "DELETED").all()
    assert all(u.member_until is None and u.vip_until is None for u in olds)


def test_banked_days_start_on_rejoin(sent_codes, db, monkeypatch):
    """사진 검수 전에 낸 이용권(쌓아 둔 일수)도 이어진다."""
    monkeypatch.setattr(get_settings(), "membership_enabled", True)
    monkeypatch.setattr(get_settings(), "payment_bank_name", "은행")
    a = signup(sent_codes, db, EMAIL)
    user = _user(db)
    user.member_days_banked = 28
    db.commit()
    _delete(a)
    signup(sent_codes, db, EMAIL)
    assert _user(db).member_days_banked == 28  # 아직 사진이 없으니 쌓아 둔 그대로


def test_match_suspension_carries_over(sent_codes, db):
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, EMAIL)
    uid = str(_user(db).id)
    r = admin.patch(f"/api/v1/admin/users/{uid}/match-suspension", json={"suspended": True, "reason": "테스트 정지"})
    assert r.status_code == 200, r.text
    _delete(a)
    _rejoin(sent_codes, db)
    assert _user(db).match_suspended is True
