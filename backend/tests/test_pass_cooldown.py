"""2026-10-02 PASS한 사람이 48시간 뒤 다시 추천에 나오는지 테스트.

- PASS 직후 ~ 48시간 안: 추천에 안 나온다
- 48시간이 지나면: 다시 나온다. 단 "처음 보는 사람" 뒤에 나온다
- 다시 PASS하면 그때부터 또 48시간 동안 안 나온다
- 다시 나온 사람에게 LIKE하면 하루 LIKE 개수에 제대로 들어간다 (하루 5개 제한을 피할 수 없다)
- LIKE한 사람은 계속 안 나온다
"""

import uuid
from datetime import timedelta

from app.models import Like, PublicProfile
from tests.conftest import admin_login, discover_ids, ready_user


def _user_id(db, client):
    return db.query(PublicProfile).filter(PublicProfile.id == uuid.UUID(client.profile_id)).one().user_id


def _age_actions(db, from_client, hours: int) -> None:
    """from_client가 남긴 LIKE/PASS 기록을 hours시간 전에 한 것으로 바꾼다."""
    uid = _user_id(db, from_client)
    for row in db.query(Like).filter(Like.from_user_id == uid):
        row.created_at = row.created_at - timedelta(hours=hours)
        row.updated_at = row.updated_at - timedelta(hours=hours)
    db.commit()


def test_passed_profile_comes_back_after_48_hours(sent_codes, db):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="FEMALE", want="MALE")
    other = ready_user(sent_codes, db, admin, "o@hufs.ac.kr", gender="MALE", want="FEMALE")

    assert me.post("/api/v1/passes", json={"profile_id": other.profile_id}).status_code == 200
    assert other.profile_id not in discover_ids(me)

    _age_actions(db, me, 47)  # 아직 48시간 안 됨
    assert other.profile_id not in discover_ids(me)

    _age_actions(db, me, 2)  # 이제 49시간 지남
    assert other.profile_id in discover_ids(me)


def test_passing_again_restarts_the_48_hours(sent_codes, db):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="FEMALE", want="MALE")
    other = ready_user(sent_codes, db, admin, "o@hufs.ac.kr", gender="MALE", want="FEMALE")

    me.post("/api/v1/passes", json={"profile_id": other.profile_id})
    _age_actions(db, me, 49)
    assert other.profile_id in discover_ids(me)

    assert me.post("/api/v1/passes", json={"profile_id": other.profile_id}).status_code == 200
    assert other.profile_id not in discover_ids(me)


def test_returning_profiles_are_drawn_like_new_ones(sent_codes, db):
    """2026-10-24 재설계: 다시 나온 사람(PASS 48시간 뒤)도 처음 보는 사람과 같은 가중치로 추첨된다."""
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="FEMALE", want="MALE", tier="HIGH")
    old = ready_user(sent_codes, db, admin, "old@hufs.ac.kr", gender="MALE", want="FEMALE", tier="HIGH")
    me.post("/api/v1/passes", json={"profile_id": old.profile_id})
    _age_actions(db, me, 49)
    new = ready_user(sent_codes, db, admin, "new@hufs.ac.kr", gender="MALE", want="FEMALE", tier="HIGH")
    firsts = {discover_ids(me)[0] for _ in range(30)}
    assert firsts == {old.profile_id, new.profile_id}


def test_like_after_returning_counts_toward_daily_limit(sent_codes, db):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="FEMALE", want="MALE")
    targets = [ready_user(sent_codes, db, admin, f"t{i}@hufs.ac.kr", gender="MALE", want="FEMALE") for i in range(6)]

    for t in targets:
        me.post("/api/v1/passes", json={"profile_id": t.profile_id})
    _age_actions(db, me, 49)

    for i, t in enumerate(targets[:5]):
        r = me.post("/api/v1/likes", json={"profile_id": t.profile_id})
        assert r.status_code == 200, r.text
        assert r.json()["likes_left_today"] == 4 - i
    assert me.post("/api/v1/likes", json={"profile_id": targets[5].profile_id}).status_code == 429


def test_liked_profile_comes_back_after_48_hours_and_likes_add_up(sent_codes, db):
    """2026-10-24 재설계: 좋아요한 사람과 48시간 동안 매칭이 안 되면 다시 나오고, 다시 좋아요하면 횟수가 쌓인다."""
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="FEMALE", want="MALE")
    other = ready_user(sent_codes, db, admin, "o@hufs.ac.kr", gender="MALE", want="FEMALE")

    me.post("/api/v1/likes", json={"profile_id": other.profile_id})
    _age_actions(db, me, 47)
    assert other.profile_id not in discover_ids(me)
    assert me.post("/api/v1/likes", json={"profile_id": other.profile_id}).status_code == 404
    _age_actions(db, me, 2)  # 합계 49시간
    cards = me.get("/api/v1/discover").json()["profiles"]
    card = next(c for c in cards if c["profile_id"] == other.profile_id)
    assert card["my_likes"] == 1  # "좋아요 1번 보냈어요" 안내용
    r = me.post("/api/v1/likes", json={"profile_id": other.profile_id})
    assert r.status_code == 200 and r.json()["matched"] is False
    row = db.query(Like).filter(Like.from_user_id == _user_id(db, me)).one()
    db.refresh(row)
    assert row.like_count == 2 and row.action == "LIKE"
    assert other.profile_id not in discover_ids(me)  # 다시 48시간 동안 안 나옴


def test_passed_person_can_be_liked_only_after_48_hours(sent_codes, db):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="FEMALE", want="MALE")
    other = ready_user(sent_codes, db, admin, "o@hufs.ac.kr", gender="MALE", want="FEMALE")

    me.post("/api/v1/passes", json={"profile_id": other.profile_id})
    # 48시간 안에는 ID를 직접 넣어도 LIKE할 수 없다 (추천에 없는 사람)
    assert me.post("/api/v1/likes", json={"profile_id": other.profile_id}).status_code == 404

    _age_actions(db, me, 49)
    assert me.post("/api/v1/likes", json={"profile_id": other.profile_id}).status_code == 200
    rows = db.query(Like).filter(Like.from_user_id == _user_id(db, me)).all()
    assert [r.action for r in rows] == ["LIKE"]


def test_passes_made_before_this_update_also_come_back(sent_codes, db):
    """업데이트 전에 남긴 PASS 기록(DB에 직접 있는 행)도 같은 규칙: 48시간 지났으면 다시 나온다."""
    from app.core.time import utcnow

    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="FEMALE", want="MALE")
    old = ready_user(sent_codes, db, admin, "old@hufs.ac.kr", gender="MALE", want="FEMALE")
    recent = ready_user(sent_codes, db, admin, "recent@hufs.ac.kr", gender="MALE", want="FEMALE")
    me_id = _user_id(db, me)
    two_days_ago = utcnow() - timedelta(days=2, hours=1)
    db.add(Like(from_user_id=me_id, to_user_id=_user_id(db, old), action="PASS", created_at=two_days_ago, updated_at=two_days_ago))
    db.add(Like(from_user_id=me_id, to_user_id=_user_id(db, recent), action="PASS"))
    db.commit()

    page = discover_ids(me)
    assert old.profile_id in page
    assert recent.profile_id not in page


# ---------- 좋아요 쌓기 (2026-10-24 추천 재설계) ----------

def _like_again(db, me, other):
    _age_actions(db, me, 49)
    r = me.post("/api/v1/likes", json={"profile_id": other.profile_id})
    assert r.status_code == 200, r.text
    return r.json()


def test_fifth_like_matches_like_a_super_like(sent_codes, db):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="FEMALE", want="MALE")
    other = ready_user(sent_codes, db, admin, "o@hufs.ac.kr", gender="MALE", want="FEMALE")
    assert me.post("/api/v1/likes", json={"profile_id": other.profile_id}).json()["matched"] is False
    for _ in range(3):  # 2~4번째
        assert _like_again(db, me, other)["matched"] is False
    r = _like_again(db, me, other)  # 5번째
    assert r["matched"] is True
    mid = r["match_id"]

    # 받은 사람: 알림 + "좋아요 5번" 표시, 보낸 사람: 슈퍼 라이크와 같은 안전장치 (답장 전 메시지 1개)
    notes = str(other.get("/api/v1/notifications").json())
    assert "좋아요 5번으로 연결됐어요" in notes
    mine = next(m for m in me.get("/api/v1/matches").json()["matches"] if m["match_id"] == mid)
    theirs = next(m for m in other.get("/api/v1/matches").json()["matches"] if m["match_id"] == mid)
    assert mine["super_like"] == "sent" and theirs["super_like"] == "received"
    assert mine["super_like_reason"] == theirs["super_like_reason"] == "repeat_likes"
    assert me.post(f"/api/v1/matches/{mid}/messages", json={"body": "안녕하세요"}).status_code == 201
    assert me.post(f"/api/v1/matches/{mid}/messages", json={"body": "두 번째"}).status_code == 409


def test_likes_from_someone_raise_their_chance_and_survive_my_pass(sent_codes, db):
    """상대가 넘기기 해도 쌓인 좋아요는 그대로 (사용자 결정)."""
    admin = admin_login(db)
    fan = ready_user(sent_codes, db, admin, "fan@hufs.ac.kr", gender="FEMALE", want="MALE")
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    fan.post("/api/v1/likes", json={"profile_id": me.profile_id})
    me.post("/api/v1/passes", json={"profile_id": fan.profile_id})  # 내가 넘김
    _like_again(db, fan, me)
    row = db.query(Like).filter(Like.from_user_id == _user_id(db, fan)).one()
    db.refresh(row)
    assert row.like_count == 2
    from app.services import profile_service
    assert profile_service.liked_counts(db, _user_id(db, me)) == {_user_id(db, fan): 2}


def test_pass_only_row_has_zero_likes_and_like_after_pass_counts_from_one(sent_codes, db):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="FEMALE", want="MALE")
    other = ready_user(sent_codes, db, admin, "o@hufs.ac.kr", gender="MALE", want="FEMALE")
    me.post("/api/v1/passes", json={"profile_id": other.profile_id})
    row = db.query(Like).filter(Like.from_user_id == _user_id(db, me)).one()
    assert row.like_count == 0
    _like_again(db, me, other)
    db.expire_all()
    row = db.query(Like).filter(Like.from_user_id == _user_id(db, me)).one()
    assert row.like_count == 1
