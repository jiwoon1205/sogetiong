"""친구 초대 이벤트 (2026-10-24).

- 이벤트 기간에 초대 링크로 처음 가입 → 그 사람의 첫 사진 승인 때 초대한 사람에게 슈퍼 라이크 1개 (한 번만)
- 재가입·기간 밖·틀린 코드·정지된 초대자는 안 됨. 초대받은 사람은 혜택 없음
- 화면에는 누가 초대했는지 나오지 않는다 (숫자만)
"""

from datetime import timedelta

from app.core.config import get_settings
from app.core.time import utcnow
from app.models.user import User
from tests.conftest import UserClient, admin_login, approve, campus_id, choose_department, set_preferences, signup, upload_photo


def _event_on(monkeypatch, on=True):
    now = utcnow()
    monkeypatch.setattr(get_settings(), "referral_start", now - timedelta(days=1))
    monkeypatch.setattr(get_settings(), "referral_end", now + (timedelta(days=13) if on else -timedelta(hours=1)))


def _code(client) -> str:
    r = client.get("/api/v1/me/referral")
    assert r.status_code == 200, r.text
    return r.json()["code"]


def _signup_with(sent_codes, db, email, code, **kw):
    client = UserClient()
    client.post("/api/v1/auth/email/send-code", json={"email": email})
    t = client.post("/api/v1/auth/email/verify", json={"email": email, "code": sent_codes[email]}).json()["verification_ticket"]
    r = client.post(
        "/api/v1/auth/register",
        json={
            "verification_ticket": t, "password": "goodpass123", "nickname": "n_" + email.split("@")[0], "gender": "FEMALE",
            "preferred_gender": "ANY", "birth_date": "2003-05-01", "campus_id": campus_id(db, kw.get("campus", "서울캠퍼스")),
            "agree_terms": True, "agree_privacy": True, "agree_appearance_public": True, "referral_code": code,
        },
    )
    assert r.status_code == 201, r.text
    client.profile_id = client.get("/api/v1/me/profile").json()["profile_id"]
    return client


def _finish(client, db, admin):
    choose_department(client, db, "경영학부")
    set_preferences(client)
    return approve(admin, upload_photo(client))


def _super_likes(db, email):
    db.expire_all()
    return db.query(User).filter(User.email == email).one().super_likes


def test_reward_on_first_photo_approval_only_once(monkeypatch, sent_codes, db):
    _event_on(monkeypatch)
    admin = admin_login(db)
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    code = _code(a)
    assert len(code) == 6 and code == _code(a)  # 같은 코드 유지

    b = _signup_with(sent_codes, db, "b@hufs.ac.kr", code.lower())  # 소문자로 와도 인정
    assert _super_likes(db, "a@hufs.ac.kr") == 0  # 가입만으로는 안 줌
    view = a.get("/api/v1/me/referral").json()
    assert view["invited"] == 1 and view["rewarded"] == 0

    _finish(b, db, admin)
    assert _super_likes(db, "a@hufs.ac.kr") == 1
    assert _super_likes(db, "b@hufs.ac.kr") == 0  # 초대받은 사람은 혜택 없음
    assert a.get("/api/v1/me/referral").json()["rewarded"] == 1
    notes = a.get("/api/v1/notifications").json()
    assert "초대한 친구" in str(notes)

    # 재검토 사진이 다시 승인돼도 또 주지 않는다
    approve(admin, upload_photo(b))
    assert _super_likes(db, "a@hufs.ac.kr") == 1


def test_no_reward_outside_event_or_bad_code(monkeypatch, sent_codes, db):
    _event_on(monkeypatch)
    admin = admin_login(db)
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    code = _code(a)
    c = _signup_with(sent_codes, db, "c@hufs.ac.kr", "ZZZZZZ")  # 없는 코드 → 가입은 되고 기록 없음
    _finish(c, db, admin)
    _event_on(monkeypatch, on=False)
    d = _signup_with(sent_codes, db, "d@hufs.ac.kr", code)  # 기간이 끝난 뒤 가입
    _finish(d, db, admin)
    assert _super_likes(db, "a@hufs.ac.kr") == 0
    assert a.get("/api/v1/me/referral").json()["active"] is False


def test_signed_up_in_event_rewarded_even_if_approved_after(monkeypatch, sent_codes, db):
    _event_on(monkeypatch)
    admin = admin_login(db)
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    b = _signup_with(sent_codes, db, "b@hufs.ac.kr", _code(a))
    _event_on(monkeypatch, on=False)
    _finish(b, db, admin)
    assert _super_likes(db, "a@hufs.ac.kr") == 1


def test_rejoin_within_7_days_is_not_a_referral(monkeypatch, sent_codes, db):
    _event_on(monkeypatch)
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    code = _code(a)
    old = signup(sent_codes, db, "old@hufs.ac.kr")
    assert old.delete("/api/v1/me", json={"password": "goodpass123"}).status_code == 200
    _signup_with(sent_codes, db, "old@hufs.ac.kr", code)  # 탈퇴 직후 재가입
    db.expire_all()
    me = db.query(User).filter(User.email == "old@hufs.ac.kr").one()
    assert me.referred_by_id is None
    assert a.get("/api/v1/me/referral").json()["invited"] == 0


def test_rejoin_after_7_days_counts(monkeypatch, sent_codes, db):
    """2026-10-24 변경: 탈퇴하고 7일이 지난 뒤 다시 가입하면 초대로 인정한다."""
    _event_on(monkeypatch)
    admin = admin_login(db)
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    code = _code(a)
    old = signup(sent_codes, db, "old@hufs.ac.kr")
    assert old.delete("/api/v1/me", json={"password": "goodpass123"}).status_code == 200
    db.query(User).filter(User.deleted_at.isnot(None)).update({"deleted_at": utcnow() - timedelta(days=8)})
    db.commit()
    again = _signup_with(sent_codes, db, "old@hufs.ac.kr", code)
    assert a.get("/api/v1/me/referral").json()["invited"] == 1
    _finish(again, db, admin)
    assert _super_likes(db, "a@hufs.ac.kr") == 1


def test_suspended_referrer_gets_nothing_and_cap(monkeypatch, sent_codes, db):
    _event_on(monkeypatch)
    admin = admin_login(db)
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    code = _code(a)
    b = _signup_with(sent_codes, db, "b@hufs.ac.kr", code)
    c = _signup_with(sent_codes, db, "c@hufs.ac.kr", code)
    # 한도 1개
    monkeypatch.setattr(get_settings(), "referral_max_rewards", 1)
    _finish(b, db, admin)
    _finish(c, db, admin)
    assert _super_likes(db, "a@hufs.ac.kr") == 1
    # 정지된 초대자
    monkeypatch.setattr(get_settings(), "referral_max_rewards", 0)
    x = signup(sent_codes, db, "x@hufs.ac.kr")
    y = _signup_with(sent_codes, db, "y@hufs.ac.kr", _code(x))
    db.query(User).filter(User.email == "x@hufs.ac.kr").update({"status": "SUSPENDED"})
    db.commit()
    _finish(y, db, admin)
    assert _super_likes(db, "x@hufs.ac.kr") == 0


def test_invitee_never_sees_referrer_and_admin_does(monkeypatch, sent_codes, db):
    _event_on(monkeypatch)
    admin = admin_login(db)
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    b = _signup_with(sent_codes, db, "b@hufs.ac.kr", _code(a))
    me = b.get("/api/v1/me").json()
    assert "referred_by" not in str(me) and "a@hufs.ac.kr" not in str(me)
    view = b.get("/api/v1/me/referral").json()
    assert set(view) == {"active", "start", "end", "code", "invited", "rewarded", "max_rewards"}
    _finish(b, db, admin)
    db.expire_all()
    bid = db.query(User).filter(User.email == "b@hufs.ac.kr").one().id
    detail = admin.get(f"/api/v1/admin/users/{bid}").json()
    assert detail["referral"]["referred_by"] is not None and detail["referral"]["rewarded_referrer_at"]
    dash = admin.get("/api/v1/admin/dashboard").json()
    assert dash["referral_signups"] == 1 and dash["referral_rewards"] == 1
