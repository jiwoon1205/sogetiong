"""찾는 관계 변경 기록 (2026-11-15, 0039).

- 찾는 관계를 고르거나 바꿀 때마다 기록이 남는다 (같은 값을 다시 보내면 안 남음)
- 관리자 사용자 상세: relationship_goal_history(최신순), ever_casual
- 관리자 사용자 목록: ever_casual 칸, goal=EVER_CASUAL 걸러보기 (지금은 다른 값이어도 나옴)
- 탈퇴 → 재가입해도 기록이 새 계정으로 이어진다
"""

from datetime import timedelta

from app.core.time import utcnow
from app.models.profile import PublicProfile
from app.models.user import User
from tests.conftest import admin_login, ready_user, signup


def _unlock(db, email):
    """3일 쿨타임을 지난 것처럼 만든다."""
    db.expire_all()
    user = db.query(User).filter(User.email == email).one()
    p = db.query(PublicProfile).filter(PublicProfile.user_id == user.id).one()
    p.relationship_goal_changed_at = utcnow() - timedelta(days=4)
    db.commit()
    return user


def _list(admin, query=""):
    return admin.get("/api/v1/admin/users" + query).json()["users"]


def test_history_and_ever_casual(sent_codes, db):
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr")
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr")
    assert a.patch("/api/v1/me/profile", json={"relationship_goal": "CASUAL"}).status_code == 200
    # 같은 값을 다시 보내는 건 변경이 아니다
    assert a.patch("/api/v1/me/profile", json={"relationship_goal": "CASUAL", "bio": "안녕"}).status_code == 200
    _unlock(db, "a@hufs.ac.kr")
    assert a.patch("/api/v1/me/profile", json={"relationship_goal": "SERIOUS"}).status_code == 200
    assert b.patch("/api/v1/me/profile", json={"relationship_goal": "FRIEND"}).status_code == 200

    uid = str(db.query(User).filter(User.email == "a@hufs.ac.kr").one().id)
    detail = admin.get(f"/api/v1/admin/users/{uid}").json()
    assert detail["ever_casual"] is True
    assert [(h["old_goal"], h["new_goal"]) for h in detail["relationship_goal_history"]] == [
        ("CASUAL", "SERIOUS"),
        (None, "CASUAL"),
    ]
    assert all(h["source"] == "USER" for h in detail["relationship_goal_history"])

    rows = {u["user_id"]: u for u in _list(admin)}
    assert rows[uid]["ever_casual"] is True and rows[uid]["relationship_goal"] == "SERIOUS"
    assert sum(u["ever_casual"] for u in rows.values()) == 1
    assert [u["user_id"] for u in _list(admin, "?goal=EVER_CASUAL")] == [uid]


def test_history_survives_rejoin(sent_codes, db):
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    admin = admin_login(db)
    assert a.patch("/api/v1/me/profile", json={"relationship_goal": "CASUAL"}).status_code == 200
    assert a.delete("/api/v1/me", json={"password": "goodpass123"}).status_code == 200
    new = signup(sent_codes, db, "a@hufs.ac.kr")
    assert new.patch("/api/v1/me/profile", json={"relationship_goal": "SERIOUS"}).status_code == 200

    db.expire_all()
    uid = str(db.query(User).filter(User.email == "a@hufs.ac.kr").one().id)
    detail = admin.get(f"/api/v1/admin/users/{uid}").json()
    assert detail["ever_casual"] is True
    assert [h["new_goal"] for h in detail["relationship_goal_history"]] == ["SERIOUS", "CASUAL"]
    assert uid in [u["user_id"] for u in _list(admin, "?goal=EVER_CASUAL")]
