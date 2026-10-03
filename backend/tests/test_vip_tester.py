"""VIP 테스트 계정 (2026-10-02, 2026-10-03 정식 VIP 규칙으로 변경).

설정 VIP_TEST_EMAILS에 적힌 학교 메일로 가입한 계정은 돈을 내지 않아도 항상 VIP다.
2026-10-03부터 정식 VIP와 같은 규칙이다 (예전의 "LIKE 무제한", "PASS 즉시 다시 나옴"은 없어짐):
- 하루 LIKE 10개
- PASS한 사람은 24시간 뒤 다시 추천에 나온다
다른 계정은 원래 규칙(하루 5개, PASS 후 48시간) 그대로다.
"""

from app.core.config import get_settings
from tests.conftest import admin_login, discover_ids, ready_user

VIP = "wldns051205@hufs.ac.kr"


def test_vip_email_is_set_by_default():
    assert VIP in get_settings().vip_test_email_set


def test_vip_has_10_likes_a_day(sent_codes, db, monkeypatch):
    admin = admin_login(db)
    vip = ready_user(sent_codes, db, admin, VIP, gender="MALE", want="FEMALE")
    body = vip.get("/api/v1/discover").json()
    assert body["likes_left_today"] == 10 and body["daily_like_limit"] == 10
    assert body["vip"] is True and body["base_like_limit"] == 5  # 화면: "좋아요는 하루 5+5개"

    # 가입자를 많이 만들면 인증 메일 요청 제한에 걸리므로, 한도를 7개로 줄여서 "무료 5개보다 많이" 되는지 본다
    monkeypatch.setattr(get_settings(), "vip_daily_like_limit", 7)
    targets = [ready_user(sent_codes, db, admin, f"t{i}@hufs.ac.kr", gender="FEMALE", want="MALE") for i in range(8)]
    for i, t in enumerate(targets[:7]):
        r = vip.post("/api/v1/likes", json={"profile_id": t.profile_id})
        assert r.status_code == 200, r.text
        assert r.json()["likes_left_today"] == 6 - i
    assert vip.post("/api/v1/likes", json={"profile_id": targets[7].profile_id}).status_code == 429


def test_vip_sees_passed_profiles_after_24_hours(sent_codes, db):
    from datetime import timedelta

    admin = admin_login(db)
    vip = ready_user(sent_codes, db, admin, VIP, gender="MALE", want="FEMALE")
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr", gender="FEMALE", want="MALE")
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr", gender="FEMALE", want="MALE")

    assert vip.post("/api/v1/passes", json={"profile_id": a.profile_id}).status_code == 200
    assert discover_ids(vip) == [b.profile_id]  # 바로 다시 나오지는 않는다

    _age_passes(db, vip, hours=23)
    assert discover_ids(vip) == [b.profile_id]
    _age_passes(db, vip, hours=2)  # 합계 25시간 → 다시 나옴, 처음 보는 사람(b) 뒤에
    assert discover_ids(vip) == [b.profile_id, a.profile_id]

    # 다시 나온 사람에게 LIKE할 수 있다. LIKE한 사람은 더 이상 안 나온다.
    assert vip.post("/api/v1/likes", json={"profile_id": a.profile_id}).status_code == 200
    assert discover_ids(vip) == [b.profile_id]


def _age_passes(db, client, *, hours):
    """client가 한 PASS를 hours시간 전에 한 것으로 바꾼다."""
    import uuid
    from datetime import timedelta

    from app.models import Like, PublicProfile

    me = db.query(PublicProfile).filter(PublicProfile.id == uuid.UUID(client.profile_id)).one().user_id
    for row in db.query(Like).filter(Like.from_user_id == me, Like.action == "PASS"):
        row.updated_at = row.updated_at - timedelta(hours=hours)
    db.commit()


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
    assert vip.get("/api/v1/discover").json()["daily_like_limit"] == 5


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
