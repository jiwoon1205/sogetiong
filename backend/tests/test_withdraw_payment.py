"""탈퇴한 사용자의 결제는 입금 확인(기간 넣기)을 막는다 (2026-10-11).
탈퇴하면 이용권·VIP가 바로 끝나므로, 탈퇴한 계정에 기간을 넣으면 아무도 쓸 수 없다."""

from tests.conftest import admin_login, ready_user
from tests.test_free_trial import world  # noqa: F401  (fixture)
from tests.test_membership import paid_world  # noqa: F401  (fixture)


def test_cannot_confirm_payment_of_withdrawn_user(sent_codes, db, world):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    assert me.post("/api/v1/me/payment/request").status_code == 200
    pid = admin.get("/api/v1/admin/payments").json()["payments"][0]["payment_id"]
    assert me.delete("/api/v1/me", json={"password": "goodpass123"}).status_code == 200
    r = admin.post(f"/api/v1/admin/payments/{pid}/confirm")
    assert r.status_code == 409 and "탈퇴" in r.json()["detail"]
