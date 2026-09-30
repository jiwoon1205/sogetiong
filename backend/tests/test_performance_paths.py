"""최적화(2026-09-30)로 바뀐 경로가 예전과 같은 결과를 주는지 확인.

- 채팅: after=<마지막 메시지>로 새 메시지만 받기
- 알림 배지: 안 읽은 개수만 받기
- 대화 목록: 여러 대화방의 마지막 메시지·차단 여부를 한 번에 조회
- 최신 외모 평가: 여러 번 평가해도 가장 최근 것만 사용
"""

import uuid

from app.models.photo import AppearanceEvaluation
from app.models.profile import PublicProfile
from app.services import profile_service

from .conftest import admin_login, ready_user


def _match(a, b) -> str:
    a.post("/api/v1/likes", json={"profile_id": b.profile_id})
    r = b.post("/api/v1/likes", json={"profile_id": a.profile_id})
    assert r.json()["matched"] is True
    return r.json()["match_id"]


def test_messages_after_returns_only_new(sent_codes, db):
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr")
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr")
    mid = _match(a, b)
    url = f"/api/v1/matches/{mid}/messages"

    first = a.post(url, json={"body": "1"}).json()
    # 새 메시지가 없으면 빈 목록
    assert b.get(url, params={"after": first["message_id"]}).json()["messages"] == []

    a.post(url, json={"body": "2"})
    a.post(url, json={"body": "3"})
    new = b.get(url, params={"after": first["message_id"]}).json()["messages"]
    assert [m["body"] for m in new] == ["2", "3"]
    assert all(m["is_mine"] is False for m in new)

    # 다른 대화방의 메시지 ID나 없는 ID를 넣으면 평소처럼 최근 메시지를 준다
    assert [m["body"] for m in b.get(url, params={"after": str(uuid.uuid4())}).json()["messages"]] == ["1", "2", "3"]


def test_unread_count(sent_codes, db):
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr")
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr")
    unread = [n for n in b.get("/api/v1/notifications?unread_only=true").json()["notifications"]]
    assert b.get("/api/v1/notifications/unread-count").json() == {"count": len(unread)}

    _match(a, b)
    before = b.get("/api/v1/notifications/unread-count").json()["count"]
    assert before == len(unread) + 1  # MATCH_CREATED

    n = b.get("/api/v1/notifications?unread_only=true").json()["notifications"][0]
    b.patch(f"/api/v1/notifications/{n['notification_id']}", json={"read": True})
    assert b.get("/api/v1/notifications/unread-count").json()["count"] == before - 1


def test_match_list_last_message_and_block(sent_codes, db):
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr")
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr")
    c = ready_user(sent_codes, db, admin, "c@hufs.ac.kr")
    d = ready_user(sent_codes, db, admin, "d@hufs.ac.kr")
    ab, ac, _ad = _match(a, b), _match(a, c), _match(a, d)

    a.post(f"/api/v1/matches/{ab}/messages", json={"body": "b에게 1"})
    b.post(f"/api/v1/matches/{ab}/messages", json={"body": "b의 답장"})
    a.post(f"/api/v1/matches/{ac}/messages", json={"body": "c에게"})

    rows = {m["partner"]["profile_id"]: m for m in a.get("/api/v1/matches").json()["matches"]}
    assert rows[b.profile_id]["last_message"]["body"] == "b의 답장"
    assert rows[b.profile_id]["last_message"]["is_mine"] is False
    assert rows[c.profile_id]["last_message"]["body"] == "c에게"
    assert rows[d.profile_id]["last_message"] is None

    # 상대가 나를 차단하면 내 목록에서도 빠진다
    assert d.post("/api/v1/blocks", json={"profile_id": a.profile_id}).status_code in (200, 201)
    ids = [m["partner"]["profile_id"] for m in a.get("/api/v1/matches").json()["matches"]]
    assert d.profile_id not in ids and b.profile_id in ids


def test_latest_evaluation_wins(sent_codes, db):
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr", tier="LOW")
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr", tier="MID")
    uid_a = db.get(PublicProfile, uuid.UUID(a.profile_id)).user_id
    uid_b = db.get(PublicProfile, uuid.UUID(b.profile_id)).user_id
    # 관리자가 등급을 여러 번 바꾸면 평가 행이 쌓인다 → 가장 최근 것만 써야 한다
    for tier in ("HIGH", "MID", "HIGH"):
        r = admin.patch(f"/api/v1/admin/users/{uid_a}/appearance-tier", json={"tier": tier, "reason": "테스트"})
        assert r.status_code == 200, r.text
    assert db.query(AppearanceEvaluation).filter(AppearanceEvaluation.user_id == uid_a).count() == 4

    latest = profile_service.latest_evaluations(db, [uid_a, uid_b])
    assert {k: v.tier for k, v in latest.items()} == {uid_a: "HIGH", uid_b: "MID"}
    assert profile_service.latest_evaluations(db, []) == {}
    assert a.get("/api/v1/discover").status_code == 200
