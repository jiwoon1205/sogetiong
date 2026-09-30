"""가입 단계 안내 (2026-10-01): 사진 미제출/반려 → PHOTO_REQUIRED, 관리자 목록의 가입 단계."""

from tests.conftest import admin_login, choose_department, set_preferences, signup, upload_photo


def _stage(admin):
    users = admin.get("/api/v1/admin/users").json()["users"]
    return users[0]["onboarding_stage"]  # 가장 최근 가입자


def test_onboarding_stage_and_photo_messages(sent_codes, db):
    admin = admin_login(db)
    a = signup(sent_codes, db, "stage@hufs.ac.kr", gender="FEMALE", want="MALE")
    assert _stage(admin) == "PROFILE"

    choose_department(a, db, "경영학부")
    assert _stage(admin) == "PREFERENCES"

    set_preferences(a)
    assert _stage(admin) == "PHOTO"
    assert a.get("/api/v1/discover").json()["detail"] == "PHOTO_REQUIRED"

    photo = upload_photo(a)
    assert _stage(admin) == "REVIEW"
    assert a.get("/api/v1/discover").json()["detail"] == "PHOTO_APPROVAL_REQUIRED"

    # 반려되면 다시 "사진 제출 필요"
    r = admin.put(
        f"/api/v1/admin/photo-reviews/{photo}/evaluation",
        json={"decision": "REJECTED", "reject_reason": "얼굴이 잘 보이지 않아요"},
    )
    assert r.status_code == 200, r.text
    assert _stage(admin) == "PHOTO"
    assert a.get("/api/v1/discover").json()["detail"] == "PHOTO_REQUIRED"


def test_me_reports_photo_approved(sent_codes, db):
    admin = admin_login(db)
    a = signup(sent_codes, db, "me@hufs.ac.kr", gender="FEMALE", want="MALE")
    assert a.get("/api/v1/me").json()["onboarding"]["photo_approved"] is False
    choose_department(a, db, "경영학부")
    set_preferences(a)
    photo = upload_photo(a)
    r = admin.put(
        f"/api/v1/admin/photo-reviews/{photo}/evaluation",
        json={"decision": "APPROVED", "overall_impression": 7, "style": 7, "grooming": 7, "photo_vibe": 7, "tier": "MID"},
    )
    assert r.status_code == 200, r.text
    assert a.get("/api/v1/me").json()["onboarding"]["photo_approved"] is True
