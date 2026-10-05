"""탈퇴 후 재가입 테스트.

규칙
- 탈퇴하면 이메일은 가짜 주소로 바뀌고 지문(email_hash)만 남는다 → 같은 메일로 다시 가입 가능
- 탈퇴 후 바로 다시 가입할 수 있다 (2026-10-05, 예전 7일 → 0. REJOIN_COOLDOWN_DAYS로 다시 켤 수 있음)
- 다시 가입하면 사진·외모 점수·등급·재검토 대기·이용권·매칭 정지를 이어받는다
- 영구 정지(BANNED)된 계정의 메일로는 다시 가입 불가
- 예전 계정의 차단 관계는 새 계정으로 이어진다
"""

from datetime import timedelta

from app.core.time import utcnow
from app.models.user import User
from app.services.auth_service import email_fingerprint

from tests.conftest import UserClient, admin_login, discover_ids, ready_user, signup

EMAIL = "a@hufs.ac.kr"


def _delete(client: UserClient):
    r = client.delete("/api/v1/me", json={"password": "goodpass123"})
    assert r.status_code == 200, r.text


def _old_account(db) -> User:
    db.expire_all()
    return db.query(User).filter(User.email_hash == email_fingerprint(EMAIL), User.deleted_at.isnot(None)).one()


def _age_deletion(db, days=8):
    """탈퇴 시각을 과거로 돌려서 '며칠 지난 것'처럼 만든다."""
    old = _old_account(db)
    old.deleted_at = utcnow() - timedelta(days=days)
    db.commit()


def _verify_status(sent_codes, email=EMAIL):
    """인증번호 확인 단계까지 진행하고 응답을 돌려준다."""
    c = UserClient()
    assert c.post("/api/v1/auth/email/send-code", json={"email": email}).status_code == 202
    assert email in sent_codes, "탈퇴한 주소로도 가입용 인증번호가 발송되어야 한다"
    return c.post("/api/v1/auth/email/verify", json={"email": email, "code": sent_codes.pop(email)})


def test_delete_anonymizes_email(sent_codes, db):
    a = signup(sent_codes, db, EMAIL)
    _delete(a)
    old = _old_account(db)
    assert old.email != EMAIL and old.email.endswith("@deleted.invalid")
    assert old.status == "DELETED"
    assert UserClient().post("/api/v1/auth/login", json={"email": EMAIL, "password": "goodpass123"}).status_code == 401


def test_rejoin_right_away(sent_codes, db):
    a = signup(sent_codes, db, EMAIL)
    _delete(a)
    new = signup(sent_codes, db, EMAIL)  # 탈퇴 직후 바로 가입 가능
    assert new.get("/api/v1/me").json()["email"] == EMAIL
    db.expire_all()
    accounts = db.query(User).filter(User.email_hash == email_fingerprint(EMAIL)).all()
    assert sorted(u.status for u in accounts) == ["ACTIVE", "DELETED"]


def test_cooldown_can_be_turned_on(sent_codes, db, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "rejoin_cooldown_days", 7)
    _delete(signup(sent_codes, db, EMAIL))
    r = _verify_status(sent_codes)
    assert r.status_code == 403 and "7일" in r.json()["detail"]
    _age_deletion(db, days=8)
    signup(sent_codes, db, EMAIL)


def test_blocks_carry_over_to_new_account(sent_codes, db):
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, EMAIL)
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr")
    assert b.post("/api/v1/blocks", json={"profile_id": a.profile_id}).status_code == 201

    _delete(a)
    _age_deletion(db)
    a2 = ready_user(sent_codes, db, admin, EMAIL)

    # 새 계정도 B에게 추천되지 않고, B도 새 계정에게 추천되지 않는다
    assert a2.profile_id not in discover_ids(b)
    assert b.profile_id not in discover_ids(a2)


def test_banned_after_deletion_cannot_rejoin(sent_codes, db):
    admin = admin_login(db)
    a = signup(sent_codes, db, EMAIL)
    _delete(a)
    _age_deletion(db)
    old_id = str(_old_account(db).id)

    # 탈퇴한 계정도 영구 정지할 수 있다 (신고받던 사람이 탈퇴로 빠져나가는 것 방지)
    r = admin.patch(f"/api/v1/admin/users/{old_id}/status", json={"status": "BANNED", "reason": "신고 누적 후 탈퇴"})
    assert r.status_code == 200, r.text
    r = _verify_status(sent_codes)
    assert r.status_code == 403
    assert "영구 제한" in r.json()["detail"]

    # 정지를 풀면(다시 탈퇴 상태로) 재가입 가능
    r = admin.patch(f"/api/v1/admin/users/{old_id}/status", json={"status": "DELETED", "reason": "오처리 정정"})
    assert r.status_code == 200, r.text
    signup(sent_codes, db, EMAIL)


def test_admin_status_rules_for_deleted_accounts(sent_codes, db):
    admin = admin_login(db)
    a = signup(sent_codes, db, EMAIL)
    b = signup(sent_codes, db, "b@hufs.ac.kr")
    _delete(a)
    old_id = str(_old_account(db).id)
    b_id = str(db.query(User).filter(User.email == "b@hufs.ac.kr").one().id)

    # 탈퇴 계정을 ACTIVE로 되살릴 수 없다
    r = admin.patch(f"/api/v1/admin/users/{old_id}/status", json={"status": "ACTIVE", "reason": "테스트"})
    assert r.status_code == 409
    # 관리자가 멀쩡한 계정을 '탈퇴' 처리할 수 없다
    r = admin.patch(f"/api/v1/admin/users/{b_id}/status", json={"status": "DELETED", "reason": "테스트"})
    assert r.status_code == 400
    assert b.get("/api/v1/me").status_code == 200


def test_admin_sees_linked_accounts_without_email(sent_codes, db):
    admin = admin_login(db)
    _delete(signup(sent_codes, db, EMAIL))
    _age_deletion(db)
    signup(sent_codes, db, EMAIL)
    db.expire_all()
    new_id = str(db.query(User).filter(User.email == EMAIL).one().id)

    detail = admin.get(f"/api/v1/admin/users/{new_id}").json()
    assert len(detail["linked_accounts"]) == 1
    assert detail["linked_accounts"][0]["status"] == "DELETED"
    assert EMAIL not in str(detail)  # 기본 조회에는 이메일이 없다


def test_old_email_gets_no_password_reset_code(sent_codes, reset_mail, db):
    _delete(signup(sent_codes, db, EMAIL))
    assert UserClient().post("/api/v1/auth/password/reset-request", json={"email": EMAIL}).status_code == 202
    assert EMAIL not in reset_mail["codes"]
