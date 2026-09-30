"""2026-09-30 매칭 규칙 변경 테스트.

- 원하는 성별: 가입 때 필수, 본인은 못 바꿈, 관리자만 변경
- 외모 등급(상/중/하): 관리자가 평가 때 필수로 고름, 사용자에게 절대 안 보임, 같은 등급이 먼저 추천
- 나를 LIKE한 사람 우대
- 하루 LIKE 5개 (한국 시간 자정 기준)
"""

from datetime import timedelta

from app.core.config import get_settings
from app.models import AppearanceEvaluation, AuditLog, Like, PrivateProfile
from tests.conftest import UserClient, admin_login, discover_ids, ready_user, set_preferences, signup, upload_photo


def _user_id(db, client):
    import uuid

    from app.models import PublicProfile

    return db.query(PublicProfile).filter(PublicProfile.id == uuid.UUID(client.profile_id)).one().user_id


# ---------- 원하는 성별 ----------

def test_preferred_gender_is_set_at_signup_and_cannot_be_changed_by_user(sent_codes, db):
    a = signup(sent_codes, db, "a@hufs.ac.kr", gender="FEMALE", want="MALE")
    assert a.get("/api/v1/me/preferences").json()["preferred_gender"] == "MALE"

    # 매칭 조건 저장에 원하는 성별을 넣어도 무시된다
    set_preferences(a, preferred_gender="ANY")
    body = a.get("/api/v1/me/preferences").json()
    assert body["preferred_gender"] == "MALE"
    assert get_settings().support_email in body["gender_locked_message"]


def test_preferred_gender_from_signup_is_used_for_matching(sent_codes, db):
    admin = admin_login(db)
    woman = ready_user(sent_codes, db, admin, "w@hufs.ac.kr", gender="FEMALE", want="MALE")
    man = ready_user(sent_codes, db, admin, "m@hufs.ac.kr", gender="MALE", want="FEMALE")
    other_woman = ready_user(sent_codes, db, admin, "o@hufs.ac.kr", gender="FEMALE", want="ANY")
    assert discover_ids(woman) == [man.profile_id]
    # 남자는 여자를 원한다 → 남자를 원하는 woman, 상관없음인 other_woman 둘 다 보인다
    assert set(discover_ids(man)) == {woman.profile_id, other_woman.profile_id}
    # other_woman(상관없음)에게 woman은 안 보인다: woman은 남자만 원하므로 양쪽 조건이 안 맞음
    assert discover_ids(other_woman) == [man.profile_id]


def test_admin_can_change_gender_with_audit_log(sent_codes, db):
    admin = admin_login(db)
    a = signup(sent_codes, db, "a@hufs.ac.kr", gender="FEMALE", want="MALE")
    uid = _user_id(db, a)

    r = admin.patch(f"/api/v1/admin/users/{uid}/gender", json={"preferred_gender": "ANY", "reason": "가입 메일로 요청"})
    assert r.status_code == 200, r.text
    assert r.json()["preferred_gender"] == "ANY" and r.json()["gender"] == "FEMALE"
    assert a.get("/api/v1/me/preferences").json()["preferred_gender"] == "ANY"
    log = db.query(AuditLog).filter(AuditLog.action == "USER_GENDER_CHANGE").one()
    assert log.metadata_json["before"]["preferred_gender"] == "MALE"
    assert log.metadata_json["after"]["preferred_gender"] == "ANY"

    detail = admin.get(f"/api/v1/admin/users/{uid}").json()
    assert detail["gender"] == "FEMALE" and detail["preferred_gender"] == "ANY"

    # 바꿀 항목이 없으면 거부
    assert admin.patch(f"/api/v1/admin/users/{uid}/gender", json={"reason": "없음"}).status_code == 422


def test_only_super_admin_can_change_gender(sent_codes, db):
    moderator = admin_login(db, role="MODERATOR")
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    r = moderator.patch(f"/api/v1/admin/users/{_user_id(db, a)}/gender", json={"gender": "MALE", "reason": "테스트"})
    assert r.status_code == 403


# ---------- 외모 등급 ----------

def test_approval_requires_tier(sent_codes, db):
    admin = admin_login(db)
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    photo = upload_photo(a)
    r = admin.put(
        f"/api/v1/admin/photo-reviews/{photo}/evaluation",
        json={"decision": "APPROVED", "overall_impression": 7, "style": 7, "grooming": 7, "photo_vibe": 7},
    )
    assert r.status_code == 422


def test_tier_is_never_sent_to_users(sent_codes, db):
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr", tier="HIGH")
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr", tier="HIGH")
    for url in ("/api/v1/discover", "/api/v1/me", "/api/v1/me/profile", "/api/v1/me/evaluation", "/api/v1/me/preferences"):
        text = b.get(url).text
        assert "tier" not in text and "HIGH" not in text, url
    b.post("/api/v1/likes", json={"profile_id": a.profile_id})
    r = a.post("/api/v1/likes", json={"profile_id": b.profile_id})
    for url in ("/api/v1/matches", f"/api/v1/matches/{r.json()['match_id']}"):
        text = a.get(url).text
        assert "tier" not in text and "HIGH" not in text, url


def test_same_tier_is_recommended_first(sent_codes, db):
    admin = admin_login(db)
    viewer = ready_user(sent_codes, db, admin, "v@hufs.ac.kr", gender="FEMALE", want="MALE", tier="HIGH")
    low = ready_user(sent_codes, db, admin, "l@hufs.ac.kr", gender="MALE", want="FEMALE", tier="LOW")
    mid = ready_user(sent_codes, db, admin, "m@hufs.ac.kr", gender="MALE", want="FEMALE", tier="MID")
    high = ready_user(sent_codes, db, admin, "h@hufs.ac.kr", gender="MALE", want="FEMALE", tier="HIGH")
    assert discover_ids(viewer) == [high.profile_id, mid.profile_id, low.profile_id]


def test_user_without_tier_cannot_discover_and_is_hidden(sent_codes, db):
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr")
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr")
    # 등급 기능 이전의 평가처럼 등급을 비운다
    uid = _user_id(db, a)
    db.query(AppearanceEvaluation).filter(AppearanceEvaluation.user_id == uid).update({"tier": None})
    db.commit()

    assert a.get("/api/v1/discover").json()["detail"] == "EVALUATION_REQUIRED"
    assert a.post("/api/v1/likes", json={"profile_id": b.profile_id}).status_code == 409
    assert a.profile_id not in discover_ids(b)
    assert admin.get(f"/api/v1/admin/users/{uid}").json()["appearance_tier"] is None

    # 관리자가 등급만 다시 정하면 된다 (점수는 그대로, 이력은 새 행으로)
    r = admin.patch(f"/api/v1/admin/users/{uid}/appearance-tier", json={"tier": "MID", "reason": "등급 기능 도입"})
    assert r.status_code == 200, r.text
    assert a.get("/api/v1/discover").status_code == 200
    assert a.profile_id in discover_ids(b)
    assert db.query(AppearanceEvaluation).filter(AppearanceEvaluation.user_id == uid).count() == 2
    assert db.query(AuditLog).filter(AuditLog.action == "EVALUATION_TIER_CHANGE").count() == 1


# ---------- 나를 LIKE한 사람 우대 ----------

def test_someone_who_liked_me_gets_onto_my_first_page(sent_codes, db, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "liked_me_probability", 1.0)
    monkeypatch.setattr(settings, "discover_page_size", 2)
    admin = admin_login(db)
    viewer = ready_user(sent_codes, db, admin, "v@hufs.ac.kr", gender="FEMALE", want="MALE", tier="MID")
    others = [
        ready_user(sent_codes, db, admin, f"m{i}@hufs.ac.kr", gender="MALE", want="FEMALE", tier="MID") for i in range(4)
    ]
    first_page = discover_ids(viewer)
    fan = next(o for o in others if o.profile_id not in first_page)
    assert fan.post("/api/v1/likes", json={"profile_id": viewer.profile_id}).status_code == 200

    page = discover_ids(viewer)
    assert fan.profile_id in page and len(page) == 2


# ---------- 하루 LIKE 5개 ----------

def test_daily_like_limit_is_five_and_resets_next_day(sent_codes, db):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="FEMALE", want="MALE")
    targets = [ready_user(sent_codes, db, admin, f"t{i}@hufs.ac.kr", gender="MALE", want="FEMALE") for i in range(7)]

    assert me.get("/api/v1/discover").json()["likes_left_today"] == 5
    for i, t in enumerate(targets[:5]):
        r = me.post("/api/v1/likes", json={"profile_id": t.profile_id})
        assert r.status_code == 200, r.text
        assert r.json()["likes_left_today"] == 4 - i

    r = me.post("/api/v1/likes", json={"profile_id": targets[5].profile_id})
    assert r.status_code == 429
    assert "자정" in r.json()["detail"]
    assert me.get("/api/v1/discover").json()["likes_left_today"] == 0
    # PASS는 제한 없음
    assert me.post("/api/v1/passes", json={"profile_id": targets[5].profile_id}).status_code == 200

    # 하루가 지나면(어제 보낸 것으로 바꾸면) 다시 보낼 수 있다
    uid = _user_id(db, me)
    for like in db.query(Like).filter(Like.from_user_id == uid):
        like.created_at = like.created_at - timedelta(days=1)
    db.commit()
    assert me.post("/api/v1/likes", json={"profile_id": targets[6].profile_id}).status_code == 200


def test_daily_like_limit_holds_when_likes_are_sent_at_the_same_time(sent_codes, db):
    """LIKE 버튼을 빠르게 여러 번 누르거나 여러 개를 동시에 보내도 하루 5개를 넘지 못한다."""
    from concurrent.futures import ThreadPoolExecutor

    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="FEMALE", want="MALE")
    targets = [ready_user(sent_codes, db, admin, f"t{i}@hufs.ac.kr", gender="MALE", want="FEMALE") for i in range(8)]

    def send(target):
        browser = UserClient()  # 같은 로그인으로 창을 여러 개 연 것과 같다
        browser.http.cookies.update(me.http.cookies)
        return browser.post("/api/v1/likes", json={"profile_id": target.profile_id}).status_code

    with ThreadPoolExecutor(max_workers=8) as pool:
        codes = list(pool.map(send, targets))

    assert codes.count(200) == 5, codes
    assert codes.count(429) == 3, codes
    uid = _user_id(db, me)
    assert db.query(Like).filter(Like.from_user_id == uid, Like.action == "LIKE").count() == 5


def test_private_profile_keeps_preferred_gender(sent_codes, db):
    a = signup(sent_codes, db, "a@hufs.ac.kr", want="FEMALE")
    assert db.query(PrivateProfile).filter(PrivateProfile.user_id == _user_id(db, a)).one().preferred_gender == "FEMALE"
