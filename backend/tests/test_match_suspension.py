"""매칭 정지 (2026-10-05).

- 둘 중 한 명이라도 매칭 정지면, 서로 LIKE해도 매칭이 숨김(HIDDEN)으로 생기고 두 사람 모두에게 안 보인다
- 정지된 본인은 절대 알 수 없다 (응답·알림·매칭 목록·끝난 대화 어디에도 흔적 없음)
- 이미 있던 매칭은 그대로
- 정지를 풀어도 숨김 매칭은 그대로 → 관리자가 하나씩 골라서 다시 보이게 한다
"""

import uuid
from datetime import timedelta

from app.core.time import utcnow
from app.models import Match, PublicProfile, User
from app.models.admin import AuditLog
from tests.conftest import admin_login, ready_user


def uid_of(db, client) -> uuid.UUID:
    return db.query(PublicProfile).filter(PublicProfile.id == uuid.UUID(client.profile_id)).one().user_id


def suspend(admin, db, client, on=True):
    r = admin.patch(
        f"/api/v1/admin/users/{uid_of(db, client)}/match-suspension", json={"suspended": on, "reason": "테스트 사유"}
    )
    assert r.status_code == 200, r.text
    return r


def notifications(client) -> list[str]:
    return [n["type"] for n in client.get("/api/v1/notifications").json()["notifications"]]


def nothing_visible(client):
    assert client.get("/api/v1/matches").json()["matches"] == []
    assert client.get("/api/v1/matches/ended").json()["matches"] == []
    assert "MATCH_CREATED" not in notifications(client)


def test_suspended_user_match_is_hidden_from_both(sent_codes, db):
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr", gender="FEMALE")
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr", gender="MALE")
    suspend(admin, db, a)

    assert a.post("/api/v1/likes", json={"profile_id": b.profile_id}).json()["matched"] is False
    r = b.post("/api/v1/likes", json={"profile_id": a.profile_id})
    assert r.status_code == 200
    assert r.json()["matched"] is False and r.json()["match_id"] is None  # 보통 "매칭 안 됨"과 똑같다

    nothing_visible(a)
    nothing_visible(b)
    match = db.query(Match).one()
    assert match.status == "HIDDEN"
    # 매칭 ID를 알아도 열 수 없다
    assert a.get(f"/api/v1/matches/{match.id}").status_code == 404
    assert b.get(f"/api/v1/matches/{match.id}/messages").status_code == 404
    assert b.post(f"/api/v1/matches/{match.id}/messages", json={"body": "hi"}).status_code == 404
    # 서로 다시 추천되지도 않는다 (이미 LIKE했으니까)
    assert b.profile_id not in [p["profile_id"] for p in a.get("/api/v1/discover").json()["profiles"]]
    # 사용자 쪽 응답 어디에도 정지 표시가 없다
    assert "match_suspended" not in a.get("/api/v1/me").text


def test_hidden_when_partner_is_suspended_and_liked_first(sent_codes, db):
    """정지된 사람이 먼저 LIKE하고, 정지 안 된 사람이 나중에 LIKE해도 숨김."""
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr", gender="FEMALE")
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr", gender="MALE")
    suspend(admin, db, b)
    b.post("/api/v1/likes", json={"profile_id": a.profile_id})
    assert a.post("/api/v1/likes", json={"profile_id": b.profile_id}).json()["matched"] is False
    nothing_visible(a)
    nothing_visible(b)


def test_existing_match_stays(sent_codes, db):
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr", gender="FEMALE")
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr", gender="MALE")
    a.post("/api/v1/likes", json={"profile_id": b.profile_id})
    match_id = b.post("/api/v1/likes", json={"profile_id": a.profile_id}).json()["match_id"]
    suspend(admin, db, a)
    assert [m["match_id"] for m in a.get("/api/v1/matches").json()["matches"]] == [match_id]
    assert a.post(f"/api/v1/matches/{match_id}/messages", json={"body": "안녕"}).status_code == 201


def test_unsuspend_keeps_hidden_and_admin_reveals_one_by_one(sent_codes, db):
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr", gender="FEMALE")
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr", gender="MALE")
    c = ready_user(sent_codes, db, admin, "c@hufs.ac.kr", gender="MALE")
    suspend(admin, db, a)
    for other in (b, c):
        a.post("/api/v1/likes", json={"profile_id": other.profile_id})
        other.post("/api/v1/likes", json={"profile_id": a.profile_id})

    info = admin.get("/api/v1/admin/match-suspensions").json()
    assert [u["user_id"] for u in info["users"]] == [str(uid_of(db, a))]
    assert info["users"][0]["hidden_matches"] == 2
    assert len(info["hidden_matches"]) == 2
    assert all(m["reveal_blocked_reason"] is None for m in info["hidden_matches"])
    detail = admin.get(f"/api/v1/admin/users/{uid_of(db, a)}").json()
    assert detail["match_suspended"] is True and detail["hidden_matches"] == 2

    # 정지를 풀어도 숨김 매칭은 그대로
    suspend(admin, db, a, on=False)
    nothing_visible(a)
    info = admin.get("/api/v1/admin/match-suspensions").json()
    assert info["users"] == [] and len(info["hidden_matches"]) == 2

    # 하나만 골라서 다시 보이게
    b_match = db.query(Match).filter((Match.user_a_id == uid_of(db, b)) | (Match.user_b_id == uid_of(db, b))).one()
    old_created = b_match.created_at
    r = admin.post(f"/api/v1/admin/matches/{b_match.id}/reveal")
    assert r.status_code == 200, r.text
    assert [m["match_id"] for m in a.get("/api/v1/matches").json()["matches"]] == [str(b_match.id)]
    assert [m["match_id"] for m in b.get("/api/v1/matches").json()["matches"]] == [str(b_match.id)]
    assert c.get("/api/v1/matches").json()["matches"] == []
    assert "MATCH_CREATED" in notifications(a) and "MATCH_CREATED" in notifications(b)
    assert "MATCH_CREATED" not in notifications(c)
    db.expire_all()
    assert db.get(Match, b_match.id).created_at >= old_created  # 방금 매칭된 것처럼 보인다
    assert b.post(f"/api/v1/matches/{b_match.id}/messages", json={"body": "hi"}).status_code == 201

    # 이미 보이는 매칭은 다시 할 수 없다
    assert admin.post(f"/api/v1/admin/matches/{b_match.id}/reveal").status_code == 409
    assert len(admin.get("/api/v1/admin/match-suspensions").json()["hidden_matches"]) == 1
    assert db.query(AuditLog).filter(AuditLog.action == "MATCH_REVEAL").count() == 1
    assert db.query(AuditLog).filter(AuditLog.action == "MATCH_SUSPEND").count() == 1


def test_admin_can_reveal_while_still_suspended(sent_codes, db):
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr", gender="FEMALE")
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr", gender="MALE")
    suspend(admin, db, a)
    a.post("/api/v1/likes", json={"profile_id": b.profile_id})
    b.post("/api/v1/likes", json={"profile_id": a.profile_id})
    match = db.query(Match).one()
    assert admin.post(f"/api/v1/admin/matches/{match.id}/reveal").status_code == 200
    assert len(a.get("/api/v1/matches").json()["matches"]) == 1


def test_cannot_reveal_after_block_and_block_leaves_no_trace(sent_codes, db):
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr", gender="FEMALE")
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr", gender="MALE")
    suspend(admin, db, a)
    a.post("/api/v1/likes", json={"profile_id": b.profile_id})
    b.post("/api/v1/likes", json={"profile_id": a.profile_id})
    b.post("/api/v1/blocks", json={"profile_id": a.profile_id})
    nothing_visible(a)
    nothing_visible(b)  # 숨김 매칭이 "끝난 대화"로 새어 나오지 않는다
    match = db.query(Match).one()
    row = admin.get("/api/v1/admin/match-suspensions").json()["hidden_matches"][0]
    assert row["reveal_blocked_reason"] == "둘 사이에 차단이 있어요"
    assert admin.post(f"/api/v1/admin/matches/{match.id}/reveal").status_code == 409


def test_withdrawal_hidden_match_not_shown_as_ended(sent_codes, db):
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr", gender="FEMALE")
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr", gender="MALE")
    suspend(admin, db, a)
    a.post("/api/v1/likes", json={"profile_id": b.profile_id})
    b.post("/api/v1/likes", json={"profile_id": a.profile_id})
    assert a.delete("/api/v1/me", json={"password": "goodpass123"}).status_code == 200
    nothing_visible(b)
    match = db.query(Match).one()
    assert admin.post(f"/api/v1/admin/matches/{match.id}/reveal").status_code == 409


def test_suspended_likes_are_not_shown_in_liked_me(sent_codes, db):
    """받은 LIKE 목록: 정지된 사람의 LIKE는 안 보이고, 정지된 사람 본인 목록은 비어 있다."""
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr", gender="FEMALE", want="MALE")
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr", gender="FEMALE", want="MALE")
    for who in (a, b):
        who.post("/api/v1/likes", json={"profile_id": me.profile_id})
    user = db.get(User, uid_of(db, me))
    user.vip_until = utcnow() + timedelta(days=7)
    db.commit()
    suspend(admin, db, a)
    assert [p["profile_id"] for p in me.get("/api/v1/liked-me").json()["profiles"]] == [b.profile_id]
    suspend(admin, db, me)
    assert me.get("/api/v1/liked-me").json()["profiles"] == []


def test_permissions_and_hidden_filter(sent_codes, db):
    admin = admin_login(db)
    reviewer = admin_login(db, role="PHOTO_REVIEWER")
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr", gender="FEMALE")
    uid = uid_of(db, a)
    body = {"suspended": True, "reason": "테스트 사유"}
    assert reviewer.patch(f"/api/v1/admin/users/{uid}/match-suspension", json=body).status_code == 403
    assert reviewer.get("/api/v1/admin/match-suspensions").status_code == 403
    moderator = admin_login(db, role="MODERATOR")
    assert moderator.patch(f"/api/v1/admin/users/{uid}/match-suspension", json=body).status_code == 200
    assert admin.get("/api/v1/admin/matches?status=HIDDEN").status_code == 200
