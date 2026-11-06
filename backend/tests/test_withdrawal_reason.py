"""탈퇴 사유 (2026-11-07). 선택 입력, 관리자만 본다."""

from app.models.user import User
from tests.conftest import admin_login, signup


def test_reason_is_saved_and_only_admin_sees_it(sent_codes, db):
    admin = admin_login(db)
    a = signup(sent_codes, db, "a@hufs.ac.kr", gender="FEMALE")
    b = signup(sent_codes, db, "b@hufs.ac.kr", gender="MALE")
    r = a.delete("/api/v1/me", json={"password": "goodpass123", "reason": "  매칭이 잘 안 돼요  "})
    assert r.status_code == 200, r.text
    assert b.delete("/api/v1/me", json={"password": "goodpass123"}).status_code == 200  # 사유는 선택

    db.expire_all()
    uid = db.query(User.id).filter(User.deleted_nickname == "user_a").scalar()
    assert admin.get(f"/api/v1/admin/users/{uid}").json()["deleted_reason"] == "매칭이 잘 안 돼요"

    rows = admin.get("/api/v1/admin/withdrawals").json()["withdrawals"]
    assert [(x["nickname"], x["gender"], x["reason"]) for x in rows] == [
        ("user_b", "MALE", None),
        ("user_a", "FEMALE", "매칭이 잘 안 돼요"),
    ]
    assert "email" not in str(rows)


def test_reason_too_long_is_rejected(sent_codes, db):
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    r = a.delete("/api/v1/me", json={"password": "goodpass123", "reason": "가" * 501})
    assert r.status_code == 422


def test_photo_reviewer_cannot_see_withdrawals(db):
    reviewer = admin_login(db, role="PHOTO_REVIEWER")
    assert reviewer.get("/api/v1/admin/withdrawals").status_code == 403
