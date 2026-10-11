"""탈퇴 7일 뒤(사진 파일이 지워진 뒤) 재가입한 사람 (2026-10-11).

예전에는 승인 기록만 이어받아서, 볼 수 있는 사진 없이 추천에 나왔고 관리자도 사진을 볼 수 없었다.
→ 사진 단계로 돌아가 새 사진을 내야 한다. 새 사진은 첫 검수처럼 받는다 (재검토 대기·이용권 조건 없음).
"""

from datetime import timedelta

from app.core.time import utcnow
from app.services import withdrawal_service
from tests.conftest import admin_login, approve, discover_ids, jpeg_with_exif, ready_user
from tests.test_rejoin_carry_over import EMAIL, _delete, _rejoin, _user


def test_rejoin_after_photo_files_purged_must_upload_again(sent_codes, db):
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, EMAIL, gender="FEMALE", prefs={"preferred_gender": "MALE"})
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr", gender="MALE", prefs={"preferred_gender": "FEMALE"})
    _delete(a)
    # 탈퇴 7일이 지나 사진 파일이 지워짐
    withdrawal_service.purge_expired(db, now=utcnow() + timedelta(days=8))

    a2 = _rejoin(sent_codes, db, gender="FEMALE", want="MALE")
    new = _user(db)
    me = a2.get("/api/v1/me").json()["onboarding"]
    assert me["photo_approved"] is False and me["photo_reupload"] is True
    assert me["photo_status"] == "NOT_SUBMITTED"
    assert a2.profile_id not in discover_ids(b)  # 사진 없이 추천에 나오지 않는다

    detail = admin.get(f"/api/v1/admin/users/{new.id}").json()
    assert detail["photo_files_purged"] is True and detail["photos"] == []

    # 예전 평가가 방금 전이어도(재검토 대기 7일 안) 첫 검수처럼 낼 수 있다
    r = a2.post("/api/v1/me/photos", files={"files": ("p.jpg", jpeg_with_exif(), "image/jpeg")})
    assert r.status_code == 201, r.text
    detail = admin.get(f"/api/v1/admin/users/{new.id}").json()
    assert len(detail["photos"]) == 1 and detail["photo_files_purged"] is False
    assert admin.get(detail["photos"][0]["image_url"]).status_code == 200  # 관리자가 볼 수 있다
    approve(admin, detail["photos"][0]["photo_id"])
    assert a2.get("/api/v1/me").json()["onboarding"]["photo_approved"] is True
    assert a2.profile_id in discover_ids(b)


def test_rejoin_within_seven_days_keeps_photos_viewable(sent_codes, db):
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, EMAIL, gender="FEMALE", prefs={"preferred_gender": "MALE"})
    _delete(a)
    _rejoin(sent_codes, db, gender="FEMALE", want="MALE")
    new = _user(db)
    detail = admin.get(f"/api/v1/admin/users/{new.id}").json()
    assert detail["photo_files_purged"] is False and len(detail["photos"]) == 1
    assert admin.get(detail["photos"][0]["image_url"]).status_code == 200
