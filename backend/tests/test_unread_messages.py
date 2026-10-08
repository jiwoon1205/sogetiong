"""대화 목록의 안 읽은 메시지 수 (2026-10-08)."""

from .conftest import admin_login, ready_user
from .test_performance_paths import _match


def _unread(client, mid):
    return next(m for m in client.get("/api/v1/matches").json()["matches"] if m["match_id"] == mid)["unread_count"]


def test_unread_count_in_match_list(sent_codes, db):
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr")
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr")
    mid = _match(a, b)
    url = f"/api/v1/matches/{mid}/messages"
    assert _unread(a, mid) == 0 and _unread(b, mid) == 0  # 메시지 없음

    first = a.post(url, json={"body": "안녕"}).json()
    a.post(url, json={"body": "반가워"})
    assert _unread(b, mid) == 2
    assert _unread(a, mid) == 0  # 내가 보낸 건 안 셈

    # b가 대화방을 열면 0
    b.get(url)
    assert _unread(b, mid) == 0

    # 새 메시지 → 1, 대화방이 4초마다 새 것만 받아 가면(after) 다시 0
    a.post(url, json={"body": "뭐해?"})
    assert _unread(b, mid) == 1
    b.get(url, params={"after": first["message_id"]})
    assert _unread(b, mid) == 0

    # 예전 메시지 더 보기(before)는 읽음 처리하지 않는다
    a.post(url, json={"body": "또"})
    b.get(url, params={"before": first["message_id"]})
    assert _unread(b, mid) == 1

    # 답장만 보내도(대화방을 다시 받기 전) 안 읽은 수는 그대로 — 화면을 열어야 0
    b.post(url, json={"body": "응"})
    assert _unread(b, mid) == 1
    assert _unread(a, mid) == 1
