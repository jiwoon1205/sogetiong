"""가입 → 프로필 → 사진 → 관리자 평가 → 추천 → LIKE → 매칭 → 채팅 전체 흐름."""

import uuid
from pathlib import Path

from PIL import Image

from app.core.config import get_settings
from app.models import UserPhoto
from tests.conftest import (
    admin_login,
    choose_department,
    department_id,
    discover_ids,
    ready_user,
    set_preferences,
    signup,
    upload_photo,
)

PUBLIC_CARD_KEYS = {
    "profile_id", "nickname", "age", "gender", "campus", "department",
    "mbti", "bio", "ideal_type", "face_type", "height_cm", "interests", "appearance",
}


def test_full_flow_signup_to_chat(sent_codes, db):
    admin = admin_login(db)
    a = signup(sent_codes, db, "alice@hufs.ac.kr", gender="FEMALE", want="MALE")
    b = signup(sent_codes, db, "bob@hufs.ac.kr", gender="MALE", want="FEMALE")
    choose_department(b, db, "경영학부")

    # 프로필 작성
    r = a.patch(
        "/api/v1/me/profile",
        json={
            "department_id": department_id(db, "ELLT학과"),
            "show_campus": True,
            "show_department": True,
            "mbti": "intp",
            "bio": "카페와 영화를 좋아해요",
            "interests": ["카페", "영화", "여행"],
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["mbti"] == "INTP"
    assert r.json()["interests"] == ["여행", "영화", "카페"]

    # 조건이 없으면 추천 불가
    assert a.get("/api/v1/discover").status_code == 409

    set_preferences(a)
    set_preferences(b)

    # 사진을 아직 안 냈으면 "검수 대기"가 아니라 "사진 제출 필요"로 알려준다
    assert a.get("/api/v1/discover").json()["detail"] == "PHOTO_REQUIRED"

    # 사진 승인 전에는 추천 불가
    photo_a = upload_photo(a)
    assert a.get("/api/v1/discover").json()["detail"] == "PHOTO_APPROVAL_REQUIRED"
    assert a.get("/api/v1/me/photos").json()["photos"][0]["review_status"] == "PENDING"

    # 관리자 평가 (4개 항목)
    r = admin.put(
        f"/api/v1/admin/photo-reviews/{photo_a}/evaluation",
        json={"decision": "APPROVED", "overall_impression": 8, "style": 7, "grooming": 8, "photo_vibe": 9, "tier": "HIGH"},
    )
    assert r.status_code == 200, r.text
    photo_b = upload_photo(b)
    admin.put(
        f"/api/v1/admin/photo-reviews/{photo_b}/evaluation",
        json={"decision": "APPROVED", "overall_impression": 6, "style": 6, "grooming": 7, "photo_vibe": 6, "tier": "MID"},
    )
    assert a.get("/api/v1/me/evaluation").json()["scores"] == {
        "overall_impression": 8, "style": 7, "grooming": 8, "photo_vibe": 9
    }

    # 추천: 서로 보인다, 카드에는 공개 필드만 있다
    cards = b.get("/api/v1/discover").json()["profiles"]
    assert [c["profile_id"] for c in cards] == [a.profile_id]
    card = cards[0]
    assert set(card) == PUBLIC_CARD_KEYS
    assert card["appearance"] == {"overall_impression": 8, "style": 7, "grooming": 8, "photo_vibe": 9}
    assert card["age"] >= 19 and card["department"] == "ELLT학과" and card["campus"] == "서울캠퍼스"
    assert discover_ids(a) == [b.profile_id]

    # LIKE → 아직 매칭 아님 → 상대도 LIKE → 매칭
    r = a.post("/api/v1/likes", json={"profile_id": b.profile_id})
    assert r.json() == {"matched": False, "match_id": None, "likes_left_today": 4}
    r = b.post("/api/v1/likes", json={"profile_id": a.profile_id})
    assert r.json()["matched"] is True
    match_id = r.json()["match_id"]

    # 매칭된 사람은 추천에서 빠진다
    assert discover_ids(a) == []

    # 채팅
    r = a.post(f"/api/v1/matches/{match_id}/messages", json={"body": "안녕하세요 😊"})
    assert r.status_code == 201, r.text
    r = b.post(f"/api/v1/matches/{match_id}/messages", json={"body": "반가워요!"})
    assert r.status_code == 201
    msgs = b.get(f"/api/v1/matches/{match_id}/messages").json()["messages"]
    assert [(m["body"], m["is_mine"]) for m in msgs] == [("안녕하세요 😊", False), ("반가워요!", True)]
    assert "sender_user_id" not in msgs[0]

    matches = a.get("/api/v1/matches").json()["matches"]
    assert matches[0]["partner"]["profile_id"] == b.profile_id
    assert matches[0]["last_message"]["body"] == "반가워요!"

    types = [n["type"] for n in b.get("/api/v1/notifications").json()["notifications"]]
    assert "MATCH_CREATED" in types and "NEW_MESSAGE" in types and "PHOTO_REVIEWED" in types


def test_uploaded_photo_has_no_exif_and_is_private(sent_codes, db):
    a = signup(sent_codes, db, "alice@hufs.ac.kr")
    photo_id = upload_photo(a)
    photo = db.get(UserPhoto, uuid.UUID(photo_id))
    path = Path(get_settings().local_storage_dir) / photo.storage_key
    with Image.open(path) as image:
        assert not image.getexif()  # EXIF·GPS 제거됨
    # 본인에게도 저장 위치는 보내지 않는다
    assert "storage_key" not in a.get("/api/v1/me/photos").text


def test_fake_image_is_rejected(sent_codes, db):
    a = signup(sent_codes, db, "alice@hufs.ac.kr")
    r = a.post("/api/v1/me/photos", files={"file": ("evil.jpg", b"<?php echo 1; ?>", "image/jpeg")})
    assert r.status_code == 400
    r = a.post("/api/v1/me/photos", files={"file": ("a.gif", b"GIF89a....", "image/gif")})
    assert r.status_code == 400


def test_unmatch_and_block_end_chat(sent_codes, db):
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr", gender="FEMALE")
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr", gender="MALE")
    c = ready_user(sent_codes, db, admin, "c@hufs.ac.kr", gender="MALE")
    a.post("/api/v1/likes", json={"profile_id": b.profile_id})
    m1 = b.post("/api/v1/likes", json={"profile_id": a.profile_id}).json()["match_id"]
    a.post("/api/v1/likes", json={"profile_id": c.profile_id})
    m2 = c.post("/api/v1/likes", json={"profile_id": a.profile_id}).json()["match_id"]

    assert a.delete(f"/api/v1/matches/{m1}").status_code == 200
    assert b.post(f"/api/v1/matches/{m1}/messages", json={"body": "hi"}).status_code == 403

    assert a.post("/api/v1/blocks", json={"profile_id": c.profile_id}).status_code == 201
    assert c.post(f"/api/v1/matches/{m2}/messages", json={"body": "hi"}).status_code == 403
    assert [m["match_id"] for m in a.get("/api/v1/matches").json()["matches"]] == []
    # 차단 해제해도 재매칭·재추천 없음
    assert a.delete(f"/api/v1/blocks/{c.profile_id}").status_code == 200
    assert c.profile_id not in discover_ids(a)


def test_like_cannot_bypass_filters_with_direct_id(sent_codes, db):
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr", gender="FEMALE", prefs={"preferred_gender": "MALE"})
    other_woman = ready_user(sent_codes, db, admin, "w@hufs.ac.kr", gender="FEMALE")
    r = a.post("/api/v1/likes", json={"profile_id": other_woman.profile_id})
    assert r.status_code == 404


def test_report(sent_codes, db):
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr")
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr")
    r = a.post("/api/v1/reports", json={"profile_id": b.profile_id, "reason": "SPAM", "description": "광고"})
    assert r.status_code == 201, r.text
    assert a.post("/api/v1/reports", json={"profile_id": b.profile_id, "reason": "SPAM"}).status_code == 409
    assert a.post("/api/v1/reports", json={"profile_id": b.profile_id, "reason": "NOPE"}).status_code == 422

    moderator = admin_login(db, "MODERATOR")
    reports = moderator.get("/api/v1/admin/reports").json()["reports"]
    assert len(reports) == 1
    r = moderator.patch(f"/api/v1/admin/reports/{reports[0]['report_id']}", json={"status": "RESOLVED"})
    assert r.status_code == 200
    assert any(n["type"] == "REPORT_RESULT" for n in a.get("/api/v1/notifications").json()["notifications"])


def test_delete_account(sent_codes, db):
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr")
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr")
    assert a.profile_id in discover_ids(b)
    assert a.delete("/api/v1/me", json={"password": "wrong-pass1"}).status_code == 401
    assert a.delete("/api/v1/me", json={"password": "goodpass123"}).status_code == 200
    assert a.get("/api/v1/me").status_code == 401
    assert a.profile_id not in discover_ids(b)
