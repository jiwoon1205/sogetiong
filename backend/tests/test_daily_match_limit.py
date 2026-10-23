"""하루 매칭 한도 → 2026-10-24 추천 재설계 때 없앴다 (사용자 결정).

예전(2026-10-06): 한국 시간 0시부터 매칭이 3번 생기면 그날은 추천 탭에 "나를 이미 LIKE한 사람"이 안 나왔다.
지금: 매칭 수와 상관없이 나를 좋아요한 사람도 보통대로 추천에 나온다 (가중치 ③으로 오히려 더 자주).
"""

import uuid
from datetime import timedelta

from app.core.time import utcnow
from app.models import Match, PublicProfile, User
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


def test_likers_still_show_after_three_matches(sent_codes, db):
    _, w, men = setup(sent_codes, db)
    liker, other = men[3], men[4]
    liker.post("/api/v1/likes", json={"profile_id": w.profile_id})  # 나를 LIKE한 사람
    make_three_matches(w, men)
    ids = discover_ids(w)
    assert liker.profile_id in ids and other.profile_id in ids
    assert user_of(db, w).match_suspended is False
    assert db.query(Match).filter(Match.status == "HIDDEN").count() == 0
