"""찾는 관계가 다르면 좋아요 못 보냄 (2026-11-14).

- 진지한 연애 ↔ 캐주얼한 만남: 서로 좋아요·슈퍼 라이크를 못 보낸다 (409 GOAL_MISMATCH). 추천에는 그대로 나온다
- 카드에 goal_mismatch: true (추천·받은 LIKE)
- 막힐 때 좋아요·체험 좋아요·슈퍼 라이크 개수가 줄지 않는다
- 대학교 친구·아직 안 고른 사람은 누구와도 된다
"""

from app.models.user import User
from tests.conftest import admin_login, ready_user


def _pair(sent_codes, db, a_goal, b_goal):
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr", gender="FEMALE", prefs={"preferred_gender": "MALE"})
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr", gender="MALE", prefs={"preferred_gender": "FEMALE"})
    for client, goal in ((a, a_goal), (b, b_goal)):
        if goal:
            assert client.patch("/api/v1/me/profile", json={"relationship_goal": goal}).status_code == 200
    return a, b


def _card(client, profile_id):
    cards = client.get("/api/v1/discover").json()["profiles"]
    return next(c for c in cards if c["profile_id"] == profile_id)


def test_serious_and_casual_cannot_like_each_other(sent_codes, db):
    a, b = _pair(sent_codes, db, "SERIOUS", "CASUAL")
    # 추천에는 나오고, 카드에 표시가 있다
    card = _card(a, b.profile_id)
    assert card["goal_mismatch"] is True and card["relationship_goal"] == "CASUAL"
    left = a.get("/api/v1/discover").json()["likes_left_today"]

    r = a.post("/api/v1/likes", json={"profile_id": b.profile_id})
    assert r.status_code == 409 and r.json()["detail"] == "GOAL_MISMATCH"
    r = b.post("/api/v1/likes", json={"profile_id": a.profile_id})
    assert r.status_code == 409 and r.json()["detail"] == "GOAL_MISMATCH"
    # 좋아요 개수가 줄지 않았다
    assert a.get("/api/v1/discover").json()["likes_left_today"] == left
    # 여전히 추천에 나온다 (넘기기는 된다)
    assert _card(a, b.profile_id)["goal_mismatch"] is True
    assert a.post("/api/v1/passes", json={"profile_id": b.profile_id}).status_code == 200


def test_super_like_also_blocked_without_spending(sent_codes, db):
    a, b = _pair(sent_codes, db, "CASUAL", "SERIOUS")
    user = db.query(User).filter(User.email == "a@hufs.ac.kr").one()
    user.super_likes = 2
    db.commit()
    r = a.post("/api/v1/super-likes", json={"profile_id": b.profile_id})
    assert r.status_code == 409 and r.json()["detail"] == "GOAL_MISMATCH"
    db.expire_all()
    assert db.query(User).filter(User.email == "a@hufs.ac.kr").one().super_likes == 2


def test_other_combinations_are_allowed(sent_codes, db):
    a, b = _pair(sent_codes, db, "SERIOUS", "FRIEND")
    assert _card(a, b.profile_id)["goal_mismatch"] is False
    assert a.post("/api/v1/likes", json={"profile_id": b.profile_id}).status_code == 200


def test_same_goal_and_unset_allowed(sent_codes, db):
    a, b = _pair(sent_codes, db, "CASUAL", None)
    assert _card(a, b.profile_id)["goal_mismatch"] is False
    r = b.post("/api/v1/likes", json={"profile_id": a.profile_id})
    assert r.status_code == 200
    r = a.post("/api/v1/likes", json={"profile_id": b.profile_id})
    assert r.status_code == 200 and r.json()["matched"] is True
