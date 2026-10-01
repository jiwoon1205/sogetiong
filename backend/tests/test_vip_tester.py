"""VIP 테스트 계정 (2026-10-02).

설정 VIP_TEST_EMAILS에 적힌 학교 메일로 가입한 계정은
- 하루 LIKE 제한이 없다
- PASS한 사람도 새로고침하면 다시 추천에 나온다
다른 계정은 원래 규칙(하루 5개, PASS한 사람은 다시 안 나옴) 그대로다.
"""

from app.core.config import get_settings
from tests.conftest import admin_login, discover_ids, ready_user

VIP = "wldns051205@hufs.ac.kr"


def test_vip_email_is_set_by_default():
    assert VIP in get_settings().vip_test_email_set


def test_vip_has_no_daily_like_limit(sent_codes, db):
    admin = admin_login(db)
    vip = ready_user(sent_codes, db, admin, VIP, gender="MALE", want="FEMALE")
    targets = [ready_user(sent_codes, db, admin, f"t{i}@hufs.ac.kr", gender="FEMALE", want="MALE") for i in range(7)]

    for t in targets:
        r = vip.post("/api/v1/likes", json={"profile_id": t.profile_id})
        assert r.status_code == 200, r.text
        assert r.json()["likes_left_today"] == 5  # 화면의 하트가 줄지 않는다
    assert vip.get("/api/v1/discover").json()["likes_left_today"] == 5


def test_vip_sees_passed_profiles_again_and_can_like_them(sent_codes, db):
    admin = admin_login(db)
    vip = ready_user(sent_codes, db, admin, VIP, gender="MALE", want="FEMALE")
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr", gender="FEMALE", want="MALE")
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr", gender="FEMALE", want="MALE")

    assert vip.post("/api/v1/passes", json={"profile_id": a.profile_id}).status_code == 200
    assert set(discover_ids(vip)) == {a.profile_id, b.profile_id}  # PASS해도 다시 나온다

    # PASS했던 사람에게 LIKE도 할 수 있다. LIKE한 사람은 더 이상 안 나온다.
    assert vip.post("/api/v1/likes", json={"profile_id": a.profile_id}).status_code == 200
    assert discover_ids(vip) == [b.profile_id]


def test_normal_user_rules_are_unchanged(sent_codes, db):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    targets = [ready_user(sent_codes, db, admin, f"t{i}@hufs.ac.kr", gender="FEMALE", want="MALE") for i in range(7)]

    assert me.post("/api/v1/passes", json={"profile_id": targets[6].profile_id}).status_code == 200
    assert targets[6].profile_id not in discover_ids(me)
    assert me.post("/api/v1/likes", json={"profile_id": targets[6].profile_id}).status_code == 404

    for t in targets[:5]:
        assert me.post("/api/v1/likes", json={"profile_id": t.profile_id}).status_code == 200
    assert me.post("/api/v1/likes", json={"profile_id": targets[5].profile_id}).status_code == 429


def test_vip_list_can_be_turned_off(sent_codes, db, monkeypatch):
    monkeypatch.setattr(get_settings(), "vip_test_emails", "")
    admin = admin_login(db)
    vip = ready_user(sent_codes, db, admin, VIP, gender="MALE", want="FEMALE")
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr", gender="FEMALE", want="MALE")
    vip.post("/api/v1/passes", json={"profile_id": a.profile_id})
    assert discover_ids(vip) == []
