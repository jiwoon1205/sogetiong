"""탈퇴 사유 (2026-11-07 선택 글 → 2026-11-16 목록에서 하나 필수). 관리자만 본다.

- 목록에서 하나를 꼭 고른다. 기타(OTHER)만 글을 꼭 적고, 다른 사유는 글을 저장하지 않는다
- 기타 글에 아이디(메일)만 들어간 것은 막는다 (비밀번호 자동완성 문제)
- 예전 화면처럼 글만 보내면 기타로 본다
"""

import pytest

from app.models.user import User
from tests.conftest import admin_login, signup


def _uid(db, nickname):
    db.expire_all()
    return db.query(User.id).filter(User.deleted_nickname == nickname).scalar()


def test_reason_code_is_saved_and_only_admin_sees_it(sent_codes, db):
    admin = admin_login(db)
    a = signup(sent_codes, db, "a@hufs.ac.kr", gender="FEMALE")
    b = signup(sent_codes, db, "b@hufs.ac.kr", gender="MALE")
    r = a.delete("/api/v1/me", json={"password": "goodpass123", "reason_code": "OTHER", "reason": "  학교를 졸업해요  "})
    assert r.status_code == 200, r.text
    # 기타가 아니면 글은 저장하지 않는다
    r = b.delete("/api/v1/me", json={"password": "goodpass123", "reason_code": "PRICE", "reason": "무시됨"})
    assert r.status_code == 200, r.text

    detail = admin.get(f"/api/v1/admin/users/{_uid(db, 'user_a')}").json()
    assert detail["deleted_reason"] == "학교를 졸업해요" and detail["deleted_reason_label"] == "기타"

    rows = admin.get("/api/v1/admin/withdrawals").json()["withdrawals"]
    assert [(x["nickname"], x["gender"], x["reason_code"], x["reason_label"], x["reason"]) for x in rows] == [
        ("user_b", "MALE", "PRICE", "이용료 부담", None),
        ("user_a", "FEMALE", "OTHER", "기타", "학교를 졸업해요"),
    ]
    assert "email" not in str(rows)


def test_old_screen_text_only_counts_as_other(sent_codes, db):
    admin = admin_login(db)
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    assert a.delete("/api/v1/me", json={"password": "goodpass123", "reason": "그냥요"}).status_code == 200
    detail = admin.get(f"/api/v1/admin/users/{_uid(db, 'user_a')}").json()
    assert detail["deleted_reason_label"] == "기타" and detail["deleted_reason"] == "그냥요"


@pytest.mark.parametrize(
    "body",
    [
        {},  # 아무것도 안 고름
        {"reason": "   "},
        {"reason_code": "OTHER"},  # 기타인데 글 없음
        {"reason_code": "OTHER", "reason": "a@hufs.ac.kr"},
        {"reason_code": "OTHER", "reason": " A@HUFS.AC.KR "},
        {"reason_code": "OTHER", "reason": "a"},
        {"reason_code": "OTHER", "reason": "someone@gmail.com"},
        {"reason_code": "OTHER", "reason": "ㅋ"},
    ],
)
def test_reason_required_and_not_an_id(sent_codes, db, body):
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    r = a.delete("/api/v1/me", json={"password": "goodpass123", **body})
    assert r.status_code == 400, r.text
    assert a.get("/api/v1/me").status_code == 200  # 탈퇴되지 않았다


def test_unknown_code_and_too_long_are_rejected(sent_codes, db):
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    assert a.delete("/api/v1/me", json={"password": "goodpass123", "reason_code": "HATE"}).status_code == 422
    r = a.delete("/api/v1/me", json={"password": "goodpass123", "reason_code": "OTHER", "reason": "가" * 501})
    assert r.status_code == 422


def test_photo_reviewer_cannot_see_withdrawals(db):
    reviewer = admin_login(db, role="PHOTO_REVIEWER")
    assert reviewer.get("/api/v1/admin/withdrawals").status_code == 403
