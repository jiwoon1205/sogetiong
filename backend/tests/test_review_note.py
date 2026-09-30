"""사진 검수 내부 메모: 승인·반려 모두 저장되고, 다시 열면 보이고, 사용자에게는 안 보인다."""

from tests.conftest import admin_login, signup, upload_photo


def test_reject_note_is_saved_and_shown(sent_codes, db):
    admin = admin_login(db)
    a = signup(sent_codes, db, "alice@hufs.ac.kr", gender="FEMALE", want="MALE")
    photo = upload_photo(a)

    r = admin.put(
        f"/api/v1/admin/photo-reviews/{photo}/evaluation",
        json={"decision": "REJECTED", "reject_reason": "얼굴이 안 보여요", "note": "  단체사진이라 반려  "},
    )
    assert r.status_code == 200, r.text

    detail = admin.get(f"/api/v1/admin/photo-reviews/{photo}").json()
    assert detail["review_status"] == "REJECTED"
    assert detail["reject_reason"] == "얼굴이 안 보여요"
    assert detail["review_note"] == "단체사진이라 반려"

    # 사용자 쪽에는 내부 메모가 절대 나오면 안 된다
    assert "단체사진" not in a.get("/api/v1/me/photos").text


def test_approve_note_is_saved_and_shown(sent_codes, db):
    admin = admin_login(db)
    a = signup(sent_codes, db, "alice@hufs.ac.kr", gender="FEMALE", want="MALE")
    photo = upload_photo(a)

    r = admin.put(
        f"/api/v1/admin/photo-reviews/{photo}/evaluation",
        json={"decision": "APPROVED", "overall_impression": 7, "style": 7, "grooming": 7, "photo_vibe": 7, "tier": "MID", "note": "조명 어두움"},
    )
    assert r.status_code == 200, r.text

    detail = admin.get(f"/api/v1/admin/photo-reviews/{photo}").json()
    assert detail["review_note"] == "조명 어두움"
    assert detail["evaluation_history"][0]["note"] == "조명 어두움"
    assert "조명 어두움" not in a.get("/api/v1/me/photos").text
    assert "조명 어두움" not in a.get("/api/v1/me/evaluation").text


def test_blank_note_is_stored_as_empty(sent_codes, db):
    admin = admin_login(db)
    a = signup(sent_codes, db, "alice@hufs.ac.kr", gender="FEMALE", want="MALE")
    photo = upload_photo(a)
    admin.put(
        f"/api/v1/admin/photo-reviews/{photo}/evaluation",
        json={"decision": "REJECTED", "reject_reason": "흐려요", "note": "   "},
    )
    assert admin.get(f"/api/v1/admin/photo-reviews/{photo}").json()["review_note"] is None
