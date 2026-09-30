"""설계도 §65 '반드시 통과해야 하는 보안 테스트' + 로그인 보안."""

import uuid
from datetime import date

import pyotp

from app.models import AuditLog, UserPhoto
from tests.conftest import (
    AdminClient,
    UserClient,
    admin_login,
    campus_id,
    discover_ids,
    jpeg_with_exif,
    make_admin,
    ready_user,
    signup,
    upload_photo,
)

PRIVATE_WORDS = ["real_name", "phone", "student_id", "birth_date", "email", "storage_key", "excluded", "preferred_gender", "user_id"]


# ---------- §65 Test 1~8 ----------

def test_1_other_users_private_profile_is_never_sent(sent_codes, db):
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr")
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr")
    a.post("/api/v1/likes", json={"profile_id": b.profile_id})
    match_id = b.post("/api/v1/likes", json={"profile_id": a.profile_id}).json()["match_id"]
    for text in (
        a.get("/api/v1/discover").text,
        a.get("/api/v1/matches").text,
        a.get(f"/api/v1/matches/{match_id}").text,
    ):
        for word in PRIVATE_WORDS:
            assert word not in text, word
    # 다른 사람 프로필을 ID로 직접 조회하는 API 자체가 없다
    assert a.get(f"/api/v1/profiles/{b.profile_id}").status_code == 404


def test_2_photo_id_alone_gives_no_access(sent_codes, db):
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    b = signup(sent_codes, db, "b@hufs.ac.kr")
    photo_id = upload_photo(b)
    assert a.get(f"/api/v1/admin/photo-reviews/{photo_id}/image").status_code == 401
    assert a.get(f"/api/v1/admin/photo-reviews/{photo_id}").status_code == 401


def test_3_user_cannot_call_admin_api(sent_codes, db):
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    for url in ("/api/v1/admin/users", "/api/v1/admin/photo-reviews", "/api/v1/admin/audit-logs"):
        assert a.get(url).status_code == 401
    # 사용자 세션 토큰을 관리자 헤더로 보내도 안 된다
    token_client = UserClient()
    r = token_client.post(
        "/api/v1/auth/login", json={"email": "a@hufs.ac.kr", "password": "goodpass123"}, headers={"X-Client-Type": "app"}
    )
    token = r.json()["session_token"]
    assert token_client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_4_photo_reviewer_cannot_read_personal_info(sent_codes, db):
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    upload_photo(a)
    reviewer = admin_login(db, "PHOTO_REVIEWER")
    listing = reviewer.get("/api/v1/admin/photo-reviews").json()["photos"]
    assert len(listing) == 1 and listing[0]["subject_code"].startswith("U")
    assert "user_id" not in listing[0]
    user_id = str(db.query(UserPhoto).one().user_id)
    assert reviewer.get(f"/api/v1/admin/users/{user_id}?include_private=true").status_code == 403
    assert reviewer.get("/api/v1/admin/users").status_code == 403
    assert reviewer.get("/api/v1/admin/reports").status_code == 403

    moderator = admin_login(db, "MODERATOR")
    assert moderator.get(f"/api/v1/admin/users/{user_id}").status_code == 200
    assert moderator.get(f"/api/v1/admin/users/{user_id}?include_private=true").status_code == 403
    assert moderator.get("/api/v1/admin/photo-reviews").status_code == 403

    superadmin = admin_login(db, "SUPER_ADMIN")
    r = superadmin.get(f"/api/v1/admin/users/{user_id}?include_private=true")
    assert r.status_code == 200 and r.json()["private"]["email"] == "a@hufs.ac.kr"
    assert db.query(AuditLog).filter(AuditLog.action == "USER_PRIVATE_VIEW").count() == 1


def test_5_changing_ids_in_url_gives_nothing(sent_codes, db):
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr")
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr")
    c = ready_user(sent_codes, db, admin, "c@hufs.ac.kr")
    a.post("/api/v1/likes", json={"profile_id": b.profile_id})
    match_id = b.post("/api/v1/likes", json={"profile_id": a.profile_id}).json()["match_id"]
    assert c.get(f"/api/v1/matches/{match_id}").status_code == 404
    assert c.get(f"/api/v1/matches/{match_id}/messages").status_code == 404
    assert c.post(f"/api/v1/matches/{match_id}/messages", json={"body": "hi"}).status_code == 404
    assert c.get(f"/api/v1/matches/{uuid.uuid4()}").status_code == 404
    notif = a.get("/api/v1/notifications").json()["notifications"][0]["notification_id"]
    assert c.patch(f"/api/v1/notifications/{notif}", json={"read": True}).status_code == 404


def test_6_preferences_are_only_visible_to_owner(sent_codes, db):
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr", prefs={"exclude_same_department": True})
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr", dept="국제학부")
    assert b.get("/api/v1/me/preferences").json()["exclude_same_department"] is False
    assert a.get("/api/v1/me/preferences").json()["exclude_same_department"] is True
    assert "exclude" not in b.get("/api/v1/discover").text


def test_7_blocked_users_are_not_recommended(sent_codes, db):
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr")
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr")
    assert b.profile_id in discover_ids(a)
    a.post("/api/v1/blocks", json={"profile_id": b.profile_id})
    assert b.profile_id not in discover_ids(a)
    assert a.profile_id not in discover_ids(b)  # 차단당한 쪽에서도 안 보임
    assert b.post("/api/v1/likes", json={"profile_id": a.profile_id}).status_code == 404


def test_8_same_department_is_not_recommended_both_ways(sent_codes, db):
    admin = admin_login(db)
    # A만 "같은 과 제외"를 켬. B는 같은 과(학과 비공개), C는 다른 과
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr", dept="경영학부", prefs={"exclude_same_department": True})
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr", dept="경영학부", show_department=False)
    c = ready_user(sent_codes, db, admin, "c@hufs.ac.kr", dept="국제학부")
    assert b.profile_id not in discover_ids(a)
    assert a.profile_id not in discover_ids(b)  # B는 안 켰어도 A가 켰으므로 서로 안 보임
    assert c.profile_id in discover_ids(a)
    # ID를 직접 넣어 LIKE해도 안 된다
    assert b.post("/api/v1/likes", json={"profile_id": a.profile_id}).status_code == 404


# ---------- 매칭 조건 ----------

def test_gender_age_campus_filters_are_mutual(sent_codes, db):
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr", gender="FEMALE", prefs={"preferred_gender": "MALE"})
    gay_man = ready_user(sent_codes, db, admin, "g@hufs.ac.kr", gender="MALE", prefs={"preferred_gender": "MALE"})
    man = ready_user(sent_codes, db, admin, "m@hufs.ac.kr", gender="MALE", prefs={"preferred_gender": "FEMALE"})
    older = ready_user(sent_codes, db, admin, "o@hufs.ac.kr", gender="MALE", birth=date(1990, 1, 1), prefs={"preferred_gender": "FEMALE", "max_age": 40})
    glob = ready_user(
        sent_codes, db, admin, "gl@hufs.ac.kr", gender="MALE", campus="글로벌캠퍼스",
        prefs={"preferred_gender": "FEMALE", "campus_mode": "MY"},
    )
    ids = discover_ids(a)
    assert man.profile_id in ids
    assert gay_man.profile_id not in ids  # 상대 조건 불일치
    assert older.profile_id not in ids  # 내 나이 조건(19~30) 밖
    assert glob.profile_id not in ids  # 상대가 '내 캠퍼스만'


def test_preferences_validation(sent_codes, db):
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    base = {"preferred_gender": "ANY", "min_age": 25, "max_age": 20}
    assert a.put("/api/v1/me/preferences", json=base).status_code == 422
    base.update(min_age=19, max_age=25, campus_mode="SELECTED", campus_ids=[str(uuid.uuid4())])
    assert a.put("/api/v1/me/preferences", json=base).status_code == 400
    base["campus_ids"] = [campus_id(db)]
    assert a.put("/api/v1/me/preferences", json=base).status_code == 200


# ---------- 가입·로그인 ----------

def test_send_code_does_not_reveal_registered_email(sent_codes, db, monkeypatch):
    signup(sent_codes, db, "a@hufs.ac.kr")
    sent_codes.clear()
    notices: list[str] = []
    monkeypatch.setattr(
        "app.services.email_service.EmailService.send_already_registered_notice",
        staticmethod(lambda email: notices.append(email)),
    )
    c = UserClient()
    registered = c.post("/api/v1/auth/email/send-code", json={"email": "a@hufs.ac.kr"})
    fresh = c.post("/api/v1/auth/email/send-code", json={"email": "new@hufs.ac.kr"})
    assert registered.status_code == fresh.status_code == 202
    assert registered.json() == fresh.json()
    assert "a@hufs.ac.kr" not in sent_codes  # 가입된 주소로는 코드를 새로 만들지 않음
    assert notices == ["a@hufs.ac.kr"]  # 대신 "로그인/비밀번호 재설정" 안내 메일
    assert "new@hufs.ac.kr" in sent_codes


def test_send_code_mail_is_sent_after_response(sent_codes, db, monkeypatch):
    """메일 발송이 느리거나 실패해도 응답은 똑같다 (응답 속도·오류로 가입 여부를 알 수 없게)."""
    from app.services.email_service import EmailDeliveryError

    def broken(*args):
        raise EmailDeliveryError("smtp down")

    monkeypatch.setattr("app.services.email_service.EmailService.send_verification_code", staticmethod(broken))
    monkeypatch.setattr("app.services.email_service.EmailService.send_already_registered_notice", staticmethod(broken))
    r = UserClient().post("/api/v1/auth/email/send-code", json={"email": "new@hufs.ac.kr"})
    assert r.status_code == 202


def test_only_school_email(sent_codes, db):
    r = UserClient().post("/api/v1/auth/email/send-code", json={"email": "someone@gmail.com"})
    assert r.status_code == 400
    r = UserClient().post("/api/v1/auth/email/send-code", json={"email": "x@evilhufs.ac.kr"})
    assert r.status_code == 400


def test_wrong_code_attempts_are_limited(sent_codes, db):
    c = UserClient()
    c.post("/api/v1/auth/email/send-code", json={"email": "a@hufs.ac.kr"})
    real = sent_codes["a@hufs.ac.kr"]
    wrong = "000000" if real != "000000" else "111111"
    for _ in range(5):
        assert c.post("/api/v1/auth/email/verify", json={"email": "a@hufs.ac.kr", "code": wrong}).status_code == 400
    # 5번 틀린 뒤에는 맞는 코드도 거부
    assert c.post("/api/v1/auth/email/verify", json={"email": "a@hufs.ac.kr", "code": real}).status_code == 400


def _register(sent_codes, db, email, **overrides):
    c = UserClient()
    c.post("/api/v1/auth/email/send-code", json={"email": email})
    ticket = c.post("/api/v1/auth/email/verify", json={"email": email, "code": sent_codes[email]}).json()["verification_ticket"]
    body = {
        "verification_ticket": ticket, "password": "goodpass123", "nickname": "닉네임", "gender": "MALE", "preferred_gender": "FEMALE",
        "birth_date": "2003-01-01", "campus_id": campus_id(db),
        "agree_terms": True, "agree_privacy": True, "agree_appearance_public": True,
    }
    body.update(overrides)
    return c.post("/api/v1/auth/register", json=body), ticket


def test_register_rules(sent_codes, db):
    r, _ = _register(sent_codes, db, "young@hufs.ac.kr", birth_date=date.today().replace(year=date.today().year - 17).isoformat())
    assert r.status_code == 400  # 만 19세 미만
    r, _ = _register(sent_codes, db, "weak@hufs.ac.kr", password="1")
    assert r.status_code == 422
    r, _ = _register(sent_codes, db, "digits@hufs.ac.kr", password="12345678")
    assert r.status_code == 422
    r, _ = _register(sent_codes, db, "noagree@hufs.ac.kr", agree_appearance_public=False)
    assert r.status_code == 400
    # 성별·원하는 성별은 필수
    r, _ = _register(sent_codes, db, "nowant@hufs.ac.kr", preferred_gender=None)
    assert r.status_code == 422
    r, _ = _register(sent_codes, db, "badwant@hufs.ac.kr", preferred_gender="BOTH")
    assert r.status_code == 422
    r, ticket = _register(sent_codes, db, "ok@hufs.ac.kr")
    assert r.status_code == 201
    # 티켓은 한 번만 쓸 수 있다
    r2 = UserClient().post("/api/v1/auth/register", json={
        "verification_ticket": ticket, "password": "goodpass123", "nickname": "또가입", "gender": "MALE",
        "preferred_gender": "FEMALE", "birth_date": "2003-01-01", "campus_id": campus_id(db),
        "agree_terms": True, "agree_privacy": True, "agree_appearance_public": True,
    })
    assert r2.status_code == 400


def test_cookie_flags_and_login_case_insensitive(sent_codes, db):
    signup(sent_codes, db, "a@hufs.ac.kr")
    c = UserClient()
    r = c.post("/api/v1/auth/login", json={"email": "A@HUFS.ac.kr", "password": "goodpass123"})
    assert r.status_code == 200
    cookies = r.headers.get_list("set-cookie")
    session_cookie = next(x for x in cookies if x.startswith("session="))
    assert "HttpOnly" in session_cookie and "Secure" in session_cookie and "samesite=lax" in session_cookie.lower()
    assert "session_token" not in r.json()  # 브라우저에는 토큰 원문을 body로 주지 않음
    assert c.post("/api/v1/auth/login", json={"email": "a@hufs.ac.kr", "password": "wrongpass1"}).status_code == 401


def test_csrf_header_required_for_cookie_requests(sent_codes, db):
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    assert a.patch("/api/v1/me/profile", json={"bio": "x"}, csrf=False).status_code == 403
    assert a.patch("/api/v1/me/profile", json={"bio": "x"}, headers={"X-CSRF-Token": "fake"}, csrf=False).status_code == 403
    assert a.patch("/api/v1/me/profile", json={"bio": "x"}).status_code == 200


def test_logout_really_ends_session(sent_codes, db):
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    stolen = a.http.cookies.get("session")
    assert a.post("/api/v1/auth/logout").status_code == 200
    thief = UserClient()
    assert thief.get("/api/v1/me", headers={"Authorization": f"Bearer {stolen}"}).status_code == 401


def test_app_client_uses_bearer_token_without_csrf(sent_codes, db):
    signup(sent_codes, db, "a@hufs.ac.kr")
    app = UserClient()
    r = app.post("/api/v1/auth/login", json={"email": "a@hufs.ac.kr", "password": "goodpass123"}, headers={"X-Client-Type": "app"})
    token = r.json()["session_token"]
    assert "session" not in app.http.cookies
    r = app.http.patch("/api/v1/me/profile", json={"bio": "앱에서 수정"}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


def test_suspended_user_is_logged_out_immediately(sent_codes, db):
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    moderator = admin_login(db, "MODERATOR")
    user_id = moderator.get("/api/v1/admin/users").json()["users"][0]["user_id"]
    r = moderator.patch(f"/api/v1/admin/users/{user_id}/status", json={"status": "SUSPENDED", "reason": "신고 누적"})
    assert r.status_code == 200
    assert a.get("/api/v1/me").status_code == 401
    assert UserClient().post("/api/v1/auth/login", json={"email": "a@hufs.ac.kr", "password": "goodpass123"}).status_code == 403


# ---------- 관리자 ----------

def test_admin_requires_second_factor(sent_codes, db):
    email, secret = make_admin(db)
    c = AdminClient()
    assert c.post("/api/v1/admin/auth/login", json={"email": email, "password": "admin-password-1234"}).status_code == 200
    assert c.get("/api/v1/admin/me").status_code == 401  # 비밀번호만으로는 불가
    assert c.post("/api/v1/admin/auth/2fa", json={"code": "000000" if pyotp.TOTP(secret).now() != "000000" else "111111"}).status_code == 401
    assert c.post("/api/v1/admin/auth/2fa", json={"code": pyotp.TOTP(secret).now()}).status_code == 200
    assert c.get("/api/v1/admin/me").json()["role"] == "SUPER_ADMIN"


def test_evaluation_change_is_audited_with_before_after(sent_codes, db):
    admin = admin_login(db)
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    photo_id = upload_photo(a)
    admin.put(f"/api/v1/admin/photo-reviews/{photo_id}/evaluation", json={"decision": "APPROVED", "overall_impression": 5, "style": 5, "grooming": 5, "photo_vibe": 5, "tier": "MID"})
    admin.put(f"/api/v1/admin/photo-reviews/{photo_id}/evaluation", json={"decision": "APPROVED", "overall_impression": 6, "style": 5, "grooming": 5, "photo_vibe": 5, "tier": "HIGH"})
    log = db.query(AuditLog).filter(AuditLog.action == "EVALUATION_UPDATE").one()
    assert log.metadata_json["before"]["overall_impression"] == 5
    assert log.metadata_json["after"]["overall_impression"] == 6
    assert log.metadata_json["before"]["tier"] == "MID" and log.metadata_json["after"]["tier"] == "HIGH"
    assert a.get("/api/v1/me/evaluation").json()["scores"]["overall_impression"] == 6
    # 사진 조회는 워터마크된 이미지 + 기록
    r = admin.get(f"/api/v1/admin/photo-reviews/{photo_id}/image")
    assert r.status_code == 200 and r.headers["cache-control"].startswith("no-store")
    assert db.query(AuditLog).filter(AuditLog.action == "PHOTO_VIEW").count() == 1


def test_resubmit_limit_after_evaluation(sent_codes, db):
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr")
    r = a.post("/api/v1/me/photos", files={"file": ("x.jpg", jpeg_with_exif(), "image/jpeg")})
    assert r.status_code == 429


def test_super_admin_always_has_every_permission(sent_codes, db):
    """최고 관리자는 DB의 권한 목록이 비어 있어도 모든 관리자 기능을 쓸 수 있다."""
    from app.models import AdminRole
    from app.models.admin import ALL_PERMISSIONS

    admin = admin_login(db)
    role = db.query(AdminRole).filter(AdminRole.name == "SUPER_ADMIN").one()
    role.permissions_json = []  # 목록을 일부러 비워도
    db.commit()

    me = admin.get("/api/v1/admin/me").json()
    assert set(me["permissions"]) >= ALL_PERMISSIONS  # 화면에는 모든 권한이 보이고
    for url in ("/api/v1/admin/dashboard", "/api/v1/admin/users", "/api/v1/admin/reports", "/api/v1/admin/audit-logs",
                "/api/v1/admin/photo-reviews?status=APPROVED"):
        assert admin.get(url).status_code == 200, url  # 실제 API도 통과한다

    # 다른 역할은 여전히 목록대로만
    reviewer = admin_login(db, role="PHOTO_REVIEWER")
    assert reviewer.get("/api/v1/admin/audit-logs").status_code == 403
