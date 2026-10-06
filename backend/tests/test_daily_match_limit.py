"""하루 매칭 한도 (2026-10-06 변경).

- 한국 시간 0시부터 매칭이 3번 생기면, 그날은 추천 탭에 "나를 이미 LIKE한 사람"이 안 나온다
- 밤 12시가 지나면 자동으로 풀린다 (다음 날 또 3번이면 또 걸림)
- 본인은 절대 모른다 (응답에 아무 표시 없음), 숨김 매칭·매칭 정지를 만들지 않는다
- VIP "받은 LIKE" 목록은 그대로 보이고, 거기서 LIKE하면 보통대로 매칭된다
"""

import uuid
from datetime import timedelta

from app.core.time import utcnow
from app.models import Match, PublicProfile, User
from app.services import match_limit_service
from tests.conftest import admin_login, discover_ids, ready_user


def user_of(db, client) -> User:
    pid = uuid.UUID(client.profile_id)
    uid = db.query(PublicProfile).filter(PublicProfile.id == pid).one().user_id
    db.expire_all()
    return db.get(User, uid)


def mutual(a, b) -> dict:
    a.post("/api/v1/likes", json={"profile_id": b.profile_id})
    return b.post("/api/v1/likes", json={"profile_id": a.profile_id}).json()


def setup(sent_codes, db, n_men=5):
    admin = admin_login(db)
    w = ready_user(sent_codes, db, admin, "w@hufs.ac.kr", gender="FEMALE")
    men = [ready_user(sent_codes, db, admin, f"m{i}@hufs.ac.kr", gender="MALE") for i in range(n_men)]
    return admin, w, men


def make_three_matches(w, men):
    for m in men[:3]:
        assert mutual(w, m)["matched"] is True


def test_after_three_matches_likers_hidden_from_discover(sent_codes, db):
    _, w, men = setup(sent_codes, db)
    liker, other = men[3], men[4]
    liker.post("/api/v1/likes", json={"profile_id": w.profile_id})  # 나를 LIKE한 사람

    # 2번 매칭까지는 나를 LIKE한 사람도 추천에 나온다
    for m in men[:2]:
        mutual(w, m)
    assert liker.profile_id in discover_ids(w)

    # 3번째 매칭은 보통대로 보이고, 그 뒤로 추천에서 빠진다. LIKE 안 한 사람은 그대로 나온다
    assert mutual(w, men[2])["matched"] is True
    ids = discover_ids(w)
    assert liker.profile_id not in ids
    assert other.profile_id in ids

    # 매칭 정지·숨김 매칭은 생기지 않는다
    assert user_of(db, w).match_suspended is False
    assert db.query(Match).filter(Match.status == "HIDDEN").count() == 0


def test_user_cannot_tell(sent_codes, db):
    """한도에 닿기 전과 후의 추천 응답 모양이 같다 (카드 수만 다름)."""
    _, w, men = setup(sent_codes, db)
    before = w.get("/api/v1/discover").json()
    make_three_matches(w, men)
    after = w.get("/api/v1/discover").json()
    assert set(before) == set(after)
    for body in (after, w.get("/api/v1/me").json()):
        text = str(body).lower()
        assert "match_limit" not in text and "suspend" not in text


def test_resets_next_day(sent_codes, db):
    _, w, men = setup(sent_codes, db)
    liker = men[3]
    liker.post("/api/v1/likes", json={"profile_id": w.profile_id})
    make_three_matches(w, men)
    assert liker.profile_id not in discover_ids(w)

    # 다음 날이 되면 (매칭이 어제 것이 되면) 다시 나온다
    for match in db.query(Match).all():
        match.created_at = match.created_at - timedelta(days=1)
    db.commit()
    assert liker.profile_id in discover_ids(w)


def test_other_side_can_still_match(sent_codes, db):
    """한도에 닿은 사람을 상대가 추천에서 보고 LIKE하면 보통대로 매칭된다."""
    _, w, men = setup(sent_codes, db)
    make_three_matches(w, men)
    w.post("/api/v1/likes", json={"profile_id": men[3].profile_id})
    r = men[3].post("/api/v1/likes", json={"profile_id": w.profile_id}).json()
    assert r["matched"] is True
    assert len(w.get("/api/v1/matches").json()["matches"]) == 4


def test_vip_liked_me_list_unchanged(sent_codes, db):
    """VIP: 추천에서는 빠지지만 받은 LIKE 목록에는 그대로 나오고, 거기서 LIKE하면 매칭된다."""
    _, w, men = setup(sent_codes, db)
    user = user_of(db, w)
    user.vip_until = utcnow() + timedelta(days=10)
    db.commit()
    liker = men[3]
    liker.post("/api/v1/likes", json={"profile_id": w.profile_id})
    make_three_matches(w, men)

    assert liker.profile_id not in discover_ids(w)
    rows = w.get("/api/v1/liked-me").json()["profiles"]
    assert [r["profile_id"] for r in rows] == [liker.profile_id]

    r = w.post("/api/v1/likes", json={"profile_id": liker.profile_id}).json()
    assert r["matched"] is True
    assert user_of(db, w).match_suspended is False


def test_revealed_matches_do_not_count(sent_codes, db):
    admin, w, men = setup(sent_codes, db)
    wu = user_of(db, w)
    admin.patch(f"/api/v1/admin/users/{wu.id}/match-suspension", json={"suspended": True, "reason": "수동"})
    mutual(w, men[0])
    mutual(w, men[1])
    admin.patch(f"/api/v1/admin/users/{wu.id}/match-suspension", json={"suspended": False, "reason": "해제"})
    for m in db.query(Match).filter(Match.status == "HIDDEN").all():
        assert admin.post(f"/api/v1/admin/matches/{m.id}/reveal").status_code == 200
    mutual(w, men[2])
    assert match_limit_service.matches_today(db, wu.id) == 1
    assert match_limit_service.reached_daily_limit(db, user_of(db, w)) is False


def test_limit_zero_turns_off(sent_codes, db, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "daily_match_limit", 0)
    _, w, men = setup(sent_codes, db)
    liker = men[3]
    liker.post("/api/v1/likes", json={"profile_id": w.profile_id})
    make_three_matches(w, men)
    assert liker.profile_id in discover_ids(w)


def test_vip_tester_is_exempt(sent_codes, db, monkeypatch):
    from app.core.config import get_settings

    s = get_settings()
    monkeypatch.setattr(type(s), "vip_test_email_set", property(lambda self: {"w@hufs.ac.kr"}))
    _, w, men = setup(sent_codes, db)
    liker = men[3]
    liker.post("/api/v1/likes", json={"profile_id": w.profile_id})
    make_three_matches(w, men)
    assert liker.profile_id in discover_ids(w)
