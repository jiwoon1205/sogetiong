"""비밀번호 재설정 테스트.

흐름: POST /auth/password/reset-request (코드 발송) → POST /auth/password/reset (코드 + 새 비밀번호)
"""

from app.models.user import User

from tests.conftest import UserClient, signup

REQ = "/api/v1/auth/password/reset-request"
RESET = "/api/v1/auth/password/reset"
EMAIL = "a@hufs.ac.kr"
OLD_PW = "goodpass123"  # conftest.signup이 쓰는 비밀번호
NEW_PW = "newpass4567"


def _login(email, password):
    return UserClient().post("/api/v1/auth/login", json={"email": email, "password": password})


def test_full_reset_flow(sent_codes, reset_mail, db):
    logged_in = signup(sent_codes, db, EMAIL)  # 다른 기기에 로그인해 있는 상태
    assert logged_in.get("/api/v1/me").status_code == 200

    c = UserClient()
    assert c.post(REQ, json={"email": EMAIL}).status_code == 202
    code = reset_mail["codes"][EMAIL]

    r = c.post(RESET, json={"email": EMAIL, "code": code, "new_password": NEW_PW})
    assert r.status_code == 200, r.text

    # 모든 기기에서 로그아웃됨
    assert logged_in.get("/api/v1/me").status_code == 401
    # 예전 비밀번호는 안 되고 새 비밀번호는 됨
    assert _login(EMAIL, OLD_PW).status_code == 401
    assert _login(EMAIL, NEW_PW).status_code == 200
    # 변경 안내 메일 발송
    assert reset_mail["notices"] == [EMAIL]


def test_same_response_whether_registered_or_not(sent_codes, reset_mail, db):
    signup(sent_codes, db, EMAIL)
    c = UserClient()
    registered = c.post(REQ, json={"email": EMAIL})
    unknown = c.post(REQ, json={"email": "nobody@hufs.ac.kr"})
    assert registered.status_code == unknown.status_code == 202
    assert registered.json() == unknown.json()
    assert "nobody@hufs.ac.kr" not in reset_mail["codes"]  # 가입 안 된 주소로는 메일을 보내지 않음


def test_only_school_email(reset_mail):
    assert UserClient().post(REQ, json={"email": "a@gmail.com"}).status_code == 400


def test_code_is_single_use(sent_codes, reset_mail, db):
    signup(sent_codes, db, EMAIL)
    c = UserClient()
    c.post(REQ, json={"email": EMAIL})
    code = reset_mail["codes"][EMAIL]
    assert c.post(RESET, json={"email": EMAIL, "code": code, "new_password": NEW_PW}).status_code == 200
    assert c.post(RESET, json={"email": EMAIL, "code": code, "new_password": "another999"}).status_code == 400
    assert _login(EMAIL, NEW_PW).status_code == 200


def test_wrong_code_attempts_are_limited(sent_codes, reset_mail, db):
    signup(sent_codes, db, EMAIL)
    c = UserClient()
    c.post(REQ, json={"email": EMAIL})
    real = reset_mail["codes"][EMAIL]
    wrong = "000000" if real != "000000" else "111111"
    for _ in range(5):
        assert c.post(RESET, json={"email": EMAIL, "code": wrong, "new_password": NEW_PW}).status_code == 400
    # 5번 틀린 뒤에는 맞는 코드도 거부
    assert c.post(RESET, json={"email": EMAIL, "code": real, "new_password": NEW_PW}).status_code == 400
    assert _login(EMAIL, OLD_PW).status_code == 200  # 비밀번호는 그대로


def test_new_request_invalidates_old_code(sent_codes, reset_mail, db):
    signup(sent_codes, db, EMAIL)
    c = UserClient()
    c.post(REQ, json={"email": EMAIL})
    first = reset_mail["codes"][EMAIL]
    c.post(REQ, json={"email": EMAIL})
    second = reset_mail["codes"][EMAIL]
    if first != second:  # (100만분의 1 확률로 같은 번호가 나올 수 있음)
        assert c.post(RESET, json={"email": EMAIL, "code": first, "new_password": NEW_PW}).status_code == 400
    assert c.post(RESET, json={"email": EMAIL, "code": second, "new_password": NEW_PW}).status_code == 200


def test_signup_and_reset_codes_cannot_be_swapped(sent_codes, reset_mail, db):
    # 가입용 코드로는 비밀번호를 바꿀 수 없다
    c = UserClient()
    c.post("/api/v1/auth/email/send-code", json={"email": "new@hufs.ac.kr"})
    signup_code = sent_codes["new@hufs.ac.kr"]
    assert c.post(RESET, json={"email": "new@hufs.ac.kr", "code": signup_code, "new_password": NEW_PW}).status_code == 400

    # 재설정 코드로는 가입 인증을 할 수 없다
    signup(sent_codes, db, EMAIL)
    c.post(REQ, json={"email": EMAIL})
    reset_code = reset_mail["codes"][EMAIL]
    assert c.post("/api/v1/auth/email/verify", json={"email": EMAIL, "code": reset_code}).status_code == 400


def test_new_password_must_follow_policy(sent_codes, reset_mail, db):
    signup(sent_codes, db, EMAIL)
    c = UserClient()
    c.post(REQ, json={"email": EMAIL})
    code = reset_mail["codes"][EMAIL]
    assert c.post(RESET, json={"email": EMAIL, "code": code, "new_password": "short1"}).status_code == 422
    assert c.post(RESET, json={"email": EMAIL, "code": code, "new_password": "12345678"}).status_code == 422
    # 규칙 위반으로 거절된 요청은 코드를 소모하지 않음
    assert c.post(RESET, json={"email": EMAIL, "code": code, "new_password": NEW_PW}).status_code == 200


def test_suspended_user_gets_no_code(sent_codes, reset_mail, db):
    signup(sent_codes, db, EMAIL)
    user = db.query(User).filter(User.email == EMAIL).one()
    user.status = "SUSPENDED"
    db.commit()
    r = UserClient().post(REQ, json={"email": EMAIL})
    assert r.status_code == 202  # 응답은 같지만
    assert EMAIL not in reset_mail["codes"]  # 코드는 보내지 않음
