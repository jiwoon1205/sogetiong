"""슈퍼 VIP (2026-10-12).

- 관리자가 지정. 영구 무료 VIP (VIP 혜택 모두, 이용권 없이 이용)
- 상대의 나이·캠퍼스 조건과 무관하게 추천에 나오고, 페이지 맨 앞에 최대 2명
- 성별·차단·같은 과 제외는 지킨다
"""

from datetime import date

from app.models.admin import AuditLog
from app.models.user import User
from tests.conftest import admin_login, discover_ids, ready_user
from tests.test_membership import user_of


def _make_super(admin, db, client, enabled=True):
    uid = user_of(db, client).id
    r = admin.post(f"/api/v1/admin/users/{uid}/super-vip", json={"enabled": enabled, "reason": "운영 테스트"})
    assert r.status_code == 200, r.text
    return uid


def _viewer(sent_codes, db, admin, **kw):
    # 서울캠퍼스만, 만 20~25세만 원하는 남자
    return ready_user(
        sent_codes, db, admin, "viewer@hufs.ac.kr", gender="MALE", want="FEMALE",
        prefs={"min_age": 20, "max_age": 25, "campus_mode": "MY"}, **kw,
    )


def test_super_vip_ignores_age_and_campus_and_comes_first(sent_codes, db):
    admin = admin_login(db)
    viewer = _viewer(sent_codes, db, admin)
    normal = [
        ready_user(sent_codes, db, admin, f"n{i}@hufs.ac.kr", gender="FEMALE", want="MALE") for i in range(4)
    ]
    # 나이(만 36세)·캠퍼스(글로벌) 모두 viewer 조건 밖
    sv = ready_user(
        sent_codes, db, admin, "sv@hufs.ac.kr", gender="FEMALE", want="MALE",
        birth=date(1990, 1, 1), campus="글로벌캠퍼스", tier="LOW",
    )
    assert sv.profile_id not in discover_ids(viewer)

    _make_super(admin, db, sv)
    for _ in range(5):  # 매번 맨 앞
        ids = discover_ids(viewer)
        assert ids[0] == sv.profile_id
        assert set(n.profile_id for n in normal) <= set(ids)

    # 서로 LIKE해서 매칭까지 된다 (조건 밖이어도)
    assert viewer.post("/api/v1/likes", json={"profile_id": sv.profile_id}).status_code == 200
    r = sv.post("/api/v1/likes", json={"profile_id": viewer.profile_id})
    assert r.status_code == 200 and r.json()["matched"] is True


def test_super_vip_keeps_gender_block_and_same_department(sent_codes, db):
    admin = admin_login(db)
    viewer = _viewer(sent_codes, db, admin)
    other_viewer = ready_user(sent_codes, db, admin, "w@hufs.ac.kr", gender="FEMALE", want="FEMALE")
    sv = ready_user(sent_codes, db, admin, "sv@hufs.ac.kr", gender="FEMALE", want="MALE", birth=date(1990, 1, 1))
    _make_super(admin, db, sv)
    assert discover_ids(viewer)[0] == sv.profile_id
    # 성별: 여자를 원하는 여자에게도, sv가 원하는 성별(남자)이 아니므로 안 나온다
    assert sv.profile_id not in discover_ids(other_viewer)
    # 차단하면 안 나온다
    assert viewer.post("/api/v1/blocks", json={"profile_id": sv.profile_id}).status_code == 201
    assert sv.profile_id not in discover_ids(viewer)


def test_same_department_exclusion_is_kept(sent_codes, db):
    admin = admin_login(db)
    # 둘 다 서울캠퍼스 경영학부(기본). viewer가 같은 과 제외를 켬
    viewer = ready_user(
        sent_codes, db, admin, "viewer@hufs.ac.kr", gender="MALE", want="FEMALE",
        prefs={"exclude_same_department": True},
    )
    sv = ready_user(sent_codes, db, admin, "sv@hufs.ac.kr", gender="FEMALE", want="MALE")
    _make_super(admin, db, sv)
    assert sv.profile_id not in discover_ids(viewer)


def test_super_vip_is_permanent_free_vip_and_logged(sent_codes, db):
    admin = admin_login(db)
    sv = ready_user(sent_codes, db, admin, "sv@hufs.ac.kr", gender="FEMALE", want="MALE")
    uid = _make_super(admin, db, sv)
    me = sv.get("/api/v1/me").json()
    assert me["membership"]["free"] is True and me["vip"]["active"] is True
    assert sv.get("/api/v1/discover").json()["daily_like_limit"] == 10
    detail = admin.get(f"/api/v1/admin/users/{uid}").json()
    assert detail["super_vip"] is True
    assert db.query(AuditLog).filter(AuditLog.action == "SUPER_VIP_ON").count() == 1

    _make_super(admin, db, sv, enabled=False)
    db.expire_all()
    assert db.get(User, uid).super_vip is False
    assert admin.post(f"/api/v1/admin/users/{uid}/super-vip", json={"enabled": False, "reason": "다시"}).status_code == 409
