"""탈퇴한 사용자 관리 (2026-10-01).

1) 관리자 사용자 목록에서 탈퇴한 사람이 사라지던 문제
   원인: 탈퇴하면 공개 프로필(닉네임·성별)이 지워져서 닉네임 검색·성별 필터에서 빠졌다.
   → 탈퇴할 때 닉네임·성별을 users.deleted_*에 남겨 두고, 관리자 화면은 그 값으로 대신 보여준다.
2) 탈퇴 후 7일 동안은 프로필·사진을 관리자가 열람할 수 있고, 7일이 지나면 자동으로 지운다.
   다른 사용자에게는 탈퇴 즉시 보이지 않는다.
"""

import uuid
from datetime import timedelta

from app.core.time import utcnow
from app.models.photo import UserPhoto
from app.models.profile import PublicProfile
from app.models.user import User
from app.services import withdrawal_service
from app.services.storage_service import get_storage

from tests.conftest import admin_login, discover_ids, ready_user, signup


def _delete(client):
    assert client.delete("/api/v1/me", json={"password": "goodpass123"}).status_code == 200


def _users(admin, query=""):
    return admin.get("/api/v1/admin/users" + query).json()


def _age_deletion(db, user_id, days):
    db.expire_all()
    u = db.get(User, uuid.UUID(str(user_id)))
    u.deleted_at = utcnow() - timedelta(days=days)
    db.commit()


def test_deleted_user_found_by_nickname_and_gender_even_after_purge(sent_codes, db):
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    admin = admin_login(db)
    before = _users(admin)["users"][0]
    uid, nick, gender = before["user_id"], before["nickname"], before["gender"]
    assert nick and gender
    _delete(a)

    def check():
        for q in ["", "?status=DELETED", f"?gender={gender}", f"?nickname={nick}"]:
            rows = _users(admin, q)["users"]
            assert [(u["nickname"], u["gender"], u["status"]) for u in rows] == [(nick, gender, "DELETED")], q

    check()  # 보관 중
    _age_deletion(db, uid, days=8)
    assert withdrawal_service.purge_expired(db) == 1
    check()  # 지운 뒤에도 닉네임·성별로 찾을 수 있다

    detail = admin.get(f"/api/v1/admin/users/{uid}").json()
    assert detail["profile"] is None
    assert detail["deleted_nickname"] == nick and detail["gender"] == gender


def test_withdrawn_data_kept_7_days_for_admin_then_purged(sent_codes, db):
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr", gender="MALE", want="FEMALE")
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr", gender="FEMALE", want="MALE")
    a_profile_id = discover_ids(b)[0]
    uid = next(u["user_id"] for u in _users(admin)["users"] if u["gender"] == "MALE")
    _delete(a)

    # 다른 사용자에게는 바로 안 보인다
    assert discover_ids(b) == []
    assert b.post("/api/v1/likes", json={"profile_id": a_profile_id}).status_code == 404

    # 관리자는 7일 동안 프로필·사진을 볼 수 있다
    detail = admin.get(f"/api/v1/admin/users/{uid}").json()
    assert detail["profile"] is not None
    assert detail["data_purge_at"] is not None
    assert len(detail["photos"]) == 1
    assert admin.get(detail["photos"][0]["image_url"]).status_code == 200
    # 하지만 평가·등급 변경은 못 한다
    assert admin.patch(f"/api/v1/admin/users/{uid}/appearance-tier", json={"tier": "HIGH", "reason": "테스트"}).status_code == 409

    # 6일째: 아직 남아 있다
    _age_deletion(db, uid, days=6)
    assert withdrawal_service.purge_expired(db) == 0

    # 8일째: 지워진다
    db.expire_all()
    keys = [p.storage_key for p in db.query(UserPhoto).filter(UserPhoto.user_id == uuid.UUID(uid))]
    _age_deletion(db, uid, days=8)
    assert withdrawal_service.purge_expired(db) == 1
    db.expire_all()
    assert db.query(PublicProfile).filter(PublicProfile.user_id == uuid.UUID(uid)).count() == 0
    assert all(p.storage_key == "" and p.upload_status == "DELETED" for p in db.query(UserPhoto).filter(UserPhoto.user_id == uuid.UUID(uid)))
    for k in keys:
        try:
            get_storage().read(k)
            raise AssertionError("사진 파일이 남아 있음")
        except (FileNotFoundError, ValueError):
            pass
    detail = admin.get(f"/api/v1/admin/users/{uid}").json()
    assert detail["profile"] is None and detail["photos"] == []
    # 두 번 돌려도 괜찮다
    assert withdrawal_service.purge_expired(db) == 0


def test_dashboard_counts_withdrawn(sent_codes, db):
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    b = signup(sent_codes, db, "b@hufs.ac.kr")
    signup(sent_codes, db, "c@hufs.ac.kr")
    admin = admin_login(db)
    ids = {u["user_id"] for u in _users(admin)["users"]}
    _delete(a)
    _delete(b)
    old = next(u["user_id"] for u in _users(admin, "?status=DELETED")["users"])
    _age_deletion(db, old, days=10)
    stats = admin.get("/api/v1/admin/dashboard").json()
    assert stats["users_deleted"] == 2 and stats["users_deleted_recent"] == 1
    assert len(ids) == 3


def test_user_list_reports_total(sent_codes, db):
    signup(sent_codes, db, "a@hufs.ac.kr")
    signup(sent_codes, db, "b@hufs.ac.kr")
    body = _users(admin_login(db))
    assert body["total"] == 2 and len(body["users"]) == 2
