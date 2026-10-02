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


# ---------- VIP 테스트 계정을 PASS한 일반 사용자: 매일 다시 추천 (2026-10-02) ----------

def _pass_rows_to(db, client):
    import uuid

    from app.models import Like, PublicProfile

    target = db.query(PublicProfile).filter(PublicProfile.id == uuid.UUID(client.profile_id)).one().user_id
    return db.query(Like).filter(Like.to_user_id == target, Like.action == "PASS")


def test_pass_on_vip_hides_only_for_today(sent_codes, db):
    from datetime import timedelta

    admin = admin_login(db)
    vip = ready_user(sent_codes, db, admin, VIP, gender="MALE", want="FEMALE")
    other_man = ready_user(sent_codes, db, admin, "m@hufs.ac.kr", gender="MALE", want="FEMALE")
    her = ready_user(sent_codes, db, admin, "her@hufs.ac.kr", gender="FEMALE", want="MALE")

    her.post("/api/v1/passes", json={"profile_id": vip.profile_id})
    her.post("/api/v1/passes", json={"profile_id": other_man.profile_id})
    assert discover_ids(her) == []  # 오늘은 둘 다 안 보인다

    # 다음 날이 되면(PASS를 어제 한 것으로 바꾸면) VIP 계정만 다시 나온다
    for row in _pass_rows_to(db, vip):
        row.updated_at = row.updated_at - timedelta(days=1)
    for row in _pass_rows_to(db, other_man):
        row.updated_at = row.updated_at - timedelta(days=1)
    db.commit()
    assert discover_ids(her) == [vip.profile_id]

    # 다시 PASS하면 그날 하루 또 숨겨지고, LIKE도 할 수 있다
    her.post("/api/v1/passes", json={"profile_id": vip.profile_id})
    assert discover_ids(her) == []


def test_pass_on_vip_before_update_is_ignored_right_away(sent_codes, db, monkeypatch):
    """업데이트(서버 재시작) 전에 한 PASS는 오늘 한 것이어도 무시 → 배포하자마자 다시 보인다."""
    from app.core.time import utcnow
    from app.services import profile_service

    admin = admin_login(db)
    vip = ready_user(sent_codes, db, admin, VIP, gender="MALE", want="FEMALE")
    her = ready_user(sent_codes, db, admin, "her@hufs.ac.kr", gender="FEMALE", want="MALE")
    her.post("/api/v1/passes", json={"profile_id": vip.profile_id})
    assert discover_ids(her) == []

    monkeypatch.setattr(profile_service, "VIP_PASS_RESET_FROM", utcnow())  # 지금 업데이트를 배포했다고 가정
    assert discover_ids(her) == [vip.profile_id]


def test_like_after_expired_pass_counts_toward_daily_limit(sent_codes, db):
    from datetime import timedelta

    admin = admin_login(db)
    vip = ready_user(sent_codes, db, admin, VIP, gender="MALE", want="FEMALE")
    her = ready_user(sent_codes, db, admin, "her@hufs.ac.kr", gender="FEMALE", want="MALE")
    her.post("/api/v1/passes", json={"profile_id": vip.profile_id})
    for row in _pass_rows_to(db, vip):
        row.updated_at = row.updated_at - timedelta(days=1)
        row.created_at = row.created_at - timedelta(days=1)
    db.commit()

    r = her.post("/api/v1/likes", json={"profile_id": vip.profile_id})
    assert r.status_code == 200, r.text
    assert r.json()["likes_left_today"] == 4  # 어제 PASS가 오늘 LIKE로 바뀐 것도 오늘 개수에 들어간다


def test_pass_on_normal_user_keeps_48_hour_rule(sent_codes, db):
    """VIP 계정이 아닌 사람을 PASS한 경우는 원래 규칙(48시간) 그대로다."""
    from datetime import timedelta

    admin = admin_login(db)
    man = ready_user(sent_codes, db, admin, "m@hufs.ac.kr", gender="MALE", want="FEMALE")
    her = ready_user(sent_codes, db, admin, "her@hufs.ac.kr", gender="FEMALE", want="MALE")
    her.post("/api/v1/passes", json={"profile_id": man.profile_id})
    for row in _pass_rows_to(db, man):
        row.updated_at = row.updated_at - timedelta(days=1)
    db.commit()
    assert discover_ids(her) == []  # 하루 지나도 아직 48시간 안 됨


# ---------- VIP 계정 본인: 방금 PASS한 사람이 새 가입자를 가리지 않는다 (2026-10-02) ----------

def test_vip_sees_new_signup_before_recently_passed(sent_codes, db, monkeypatch):
    """예전 버그: VIP가 48시간 안에 PASS한 사람이 "처음 보는 사람"으로 취급돼서 10칸을 차지했다
    → 새로 가입한 사람이 추천에 안 떴다. 이제 PASS한 사람은 항상 처음 보는 사람 뒤로 간다."""
    monkeypatch.setattr(get_settings(), "discover_page_size", 3)  # 한 페이지 3명으로 줄여서 시험
    admin = admin_login(db)
    vip = ready_user(sent_codes, db, admin, VIP, gender="MALE", want="FEMALE")
    page = 3
    olds = [ready_user(sent_codes, db, admin, f"o{i}@hufs.ac.kr", gender="FEMALE", want="MALE") for i in range(page)]
    for o in olds:
        assert vip.post("/api/v1/passes", json={"profile_id": o.profile_id}).status_code == 200

    new = ready_user(sent_codes, db, admin, "new@hufs.ac.kr", gender="FEMALE", want="MALE")
    for _ in range(5):  # 새로고침을 여러 번 해도 항상 맨 앞
        assert discover_ids(vip)[0] == new.profile_id


def test_vip_passed_profiles_rotate_oldest_pass_first(sent_codes, db):
    """처음 보는 사람이 없을 때는 PASS한 지 오래된 사람부터 → 새로고침마다 같은 사람만 나오지 않는다."""
    from datetime import timedelta

    admin = admin_login(db)
    vip = ready_user(sent_codes, db, admin, VIP, gender="MALE", want="FEMALE")
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr", gender="FEMALE", want="MALE")
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr", gender="FEMALE", want="MALE")
    vip.post("/api/v1/passes", json={"profile_id": a.profile_id})
    vip.post("/api/v1/passes", json={"profile_id": b.profile_id})
    for row in _pass_rows_to(db, a):
        row.updated_at = row.updated_at - timedelta(hours=1)
    db.commit()
    assert discover_ids(vip) == [a.profile_id, b.profile_id]

    # a를 다시 PASS하면 a가 가장 최근 → 이번엔 b가 먼저
    vip.post("/api/v1/passes", json={"profile_id": a.profile_id})
    assert discover_ids(vip) == [b.profile_id, a.profile_id]


# ---------- VIP 테스트 계정: 사진 재검토 간격 3일 (2026-10-02) ----------

def test_vip_photo_resubmit_every_3_days(sent_codes, db):
    """일반은 마지막 평가 후 7일, VIP 테스트 계정은 3일 뒤에 다시 사진을 낼 수 있다."""
    from datetime import timedelta

    from app.core.time import utcnow
    from app.models.photo import AppearanceEvaluation
    from tests.conftest import approve, jpeg_with_exif

    admin = admin_login(db)
    vip = ready_user(sent_codes, db, admin, VIP, gender="MALE", want="FEMALE")
    assert vip.get("/api/v1/me/photos").json()["resubmit"]["wait_days"] == 3

    # 바로 재검토(평생 1번)는 일반 계정과 똑같이 있다
    r = vip.post("/api/v1/me/photos", files={"file": ("x.jpg", jpeg_with_exif(), "image/jpeg")})
    assert r.status_code == 201 and r.json()["used_free_rereview"] is True
    approve(admin, r.json()["photo_id"])
    r = vip.post("/api/v1/me/photos", files={"file": ("x.jpg", jpeg_with_exif(), "image/jpeg")})
    assert r.status_code == 429 and "3일" in r.json()["detail"]

    # 마지막 평가 후 3일이 지나면 다시 낼 수 있다 (일반 계정이면 아직 막혀 있을 때)
    for ev in db.query(AppearanceEvaluation).all():
        ev.created_at = utcnow() - timedelta(days=3, minutes=1)
    db.commit()
    assert vip.get("/api/v1/me/photos").json()["resubmit"]["allowed"] is True
    r = vip.post("/api/v1/me/photos", files={"file": ("x.jpg", jpeg_with_exif(), "image/jpeg")})
    assert r.status_code == 201, r.text
