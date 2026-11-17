"""감시 대상 (2026-11-17, 관리자 전용·사용자에게 비밀).

- 캐주얼한 만남을 안 고른 사람(대학교 친구·안 고름)이 캐주얼에게 좋아요/슈퍼 라이크 → 기록, 감시 대상
- 진지한 연애 → 캐주얼은 막히지만(GOAL_MISMATCH) 막힌 것도 기록 (1시간에 한 번만)
- 캐주얼 → 캐주얼, 친구 → 진지한 연애는 기록 안 함
- 사용자 응답에는 아무 흔적이 없다
- 관리자 목록·상세·상태/메모 변경, '문제없음'이어도 다시 보내면 '지켜보는 중'
- 캐주얼 매칭 내보내기 스크립트(deploy/casual_match_export.py)
"""

import io
import uuid
import runpy
import sys
from pathlib import Path

from app.models.watch import WatchEvent, WatchTarget
from tests.conftest import admin_login, ready_user


def _goal(client, goal):
    assert client.patch("/api/v1/me/profile", json={"relationship_goal": goal}).status_code == 200


def _setup(sent_codes, db):
    admin = admin_login(db)
    casual = ready_user(sent_codes, db, admin, "c@hufs.ac.kr", gender="FEMALE")
    friend = ready_user(sent_codes, db, admin, "f@hufs.ac.kr", gender="MALE")
    serious = ready_user(sent_codes, db, admin, "s@hufs.ac.kr", gender="MALE")
    nogoal = ready_user(sent_codes, db, admin, "n@hufs.ac.kr", gender="MALE")
    _goal(casual, "CASUAL")
    _goal(friend, "FRIEND")
    _goal(serious, "SERIOUS")
    return admin, casual, friend, serious, nogoal


def test_records_secretly_and_admin_manages(sent_codes, db):
    admin, casual, friend, serious, nogoal = _setup(sent_codes, db)

    r = friend.post("/api/v1/likes", json={"profile_id": casual.profile_id})
    assert r.status_code == 200, r.text
    assert "watch" not in r.text.lower()
    # 진지한 연애 → 캐주얼: 막힘 (사용자에게는 원래와 같은 응답), 두 번 눌러도 기록은 한 번
    for _ in range(2):
        r = serious.post("/api/v1/likes", json={"profile_id": casual.profile_id})
        assert r.status_code == 409 and r.json()["detail"] == "GOAL_MISMATCH"
    assert nogoal.post("/api/v1/likes", json={"profile_id": casual.profile_id}).status_code == 200
    # 캐주얼 → 다른 사람, 친구 → 아무나: 캐주얼이 받는 게 아니면 기록 안 함
    casual.post("/api/v1/likes", json={"profile_id": friend.profile_id})

    db.expire_all()
    events = db.query(WatchEvent).all()
    assert len(events) == 3
    assert sorted((e.actor_goal or "NONE", e.blocked) for e in events) == [("FRIEND", False), ("NONE", False), ("SERIOUS", True)]

    # 사용자 화면에는 흔적이 없다
    for c in (friend, serious, nogoal):
        for url in ("/api/v1/me", "/api/v1/discover", "/api/v1/me/profile"):
            assert "watch" not in c.get(url).text.lower()

    # 관리자 목록
    data = admin.get("/api/v1/admin/watchlist").json()
    assert data["counts"] == {"WATCHING": 3, "CLEARED": 0}
    by_code = {t["subject_code"]: t for t in data["targets"]}
    serious_row = next(t for t in data["targets"] if t["relationship_goal"] == "SERIOUS")
    assert serious_row["blocked_count"] == 1 and serious_row["event_count"] == 1
    assert len(by_code) == 3

    # 상세
    friend_row = next(t for t in data["targets"] if t["relationship_goal"] == "FRIEND")
    d = admin.get(f"/api/v1/admin/watchlist/{friend_row['user_id']}").json()
    assert d["status"] == "WATCHING" and len(d["events"]) == 1
    assert d["events"][0]["to"]["relationship_goal"] == "CASUAL" and d["events"][0]["blocked"] is False

    # 사용자 목록·상세에 표시
    users = {u["user_id"]: u for u in admin.get("/api/v1/admin/users").json()["users"]}
    assert users[friend_row["user_id"]]["watch_status"] == "WATCHING"
    assert admin.get(f"/api/v1/admin/users/{friend_row['user_id']}").json()["watch_status"] == "WATCHING"

    # 문제없음 + 메모 → 다시 보내면 지켜보는 중으로
    r = admin.patch(f"/api/v1/admin/watchlist/{friend_row['user_id']}", json={"status": "CLEARED", "note": "친구로 연락"})
    assert r.status_code == 200 and r.json()["status"] == "CLEARED"
    assert admin.get("/api/v1/admin/watchlist?status=CLEARED").json()["targets"][0]["note"] == "친구로 연락"
    other = ready_user(sent_codes, db, admin, "c2@hufs.ac.kr", gender="FEMALE")
    _goal(other, "CASUAL")
    assert friend.post("/api/v1/likes", json={"profile_id": other.profile_id}).status_code == 200
    db.expire_all()
    row = db.get(WatchTarget, uuid.UUID(friend_row["user_id"]))
    assert row.status == "WATCHING" and row.event_count == 2 and row.note == "친구로 연락"


def test_photo_reviewer_cannot_see_watchlist(db):
    reviewer = admin_login(db, role="PHOTO_REVIEWER")
    assert reviewer.get("/api/v1/admin/watchlist").status_code == 403


def test_casual_match_export_script(sent_codes, db, monkeypatch):
    admin, casual, friend, serious, nogoal = _setup(sent_codes, db)
    assert friend.post("/api/v1/likes", json={"profile_id": casual.profile_id}).status_code == 200
    r = casual.post("/api/v1/likes", json={"profile_id": friend.profile_id})
    assert r.status_code == 200 and r.json()["matched"] is True

    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stderr", err)
    runpy.run_path(str(Path(__file__).resolve().parents[2] / "deploy" / "casual_match_export.py"), run_name="__main__")
    lines = out.getvalue().lstrip("﻿").strip().splitlines()
    assert lines[0].startswith("회원코드,찾는관계(지금)")
    assert len(lines) == 2
    row = lines[1].split(",")
    assert row[1] == "대학교 친구" and row[4] == "캐주얼한 만남" and row[6] == "서로 좋아요" and row[7] == "이 사람"
    assert row[0].startswith("U") and len(row[0]) == 7
    assert "해당 매칭 1개" in err.getvalue()


def test_monitoring_counts_include_history(sent_codes, db, monkeypatch):
    """감시 목록 숫자: 캐주얼과 매칭 수·내가 먼저 시작한 수·캐주얼에게 보낸 좋아요 수 (볼 때마다 새로 셈)."""
    admin, casual, friend, serious, nogoal = _setup(sent_codes, db)
    # 캐주얼이 먼저 좋아요 → 친구가 받아서 매칭 (친구가 먼저 시작한 건 아님)
    assert casual.post("/api/v1/likes", json={"profile_id": friend.profile_id}).status_code == 200
    assert friend.post("/api/v1/likes", json={"profile_id": casual.profile_id}).json()["matched"] is True
    # 안 고름 → 다른 캐주얼에게 먼저 좋아요, 그 캐주얼이 받아서 매칭 (안 고름이 먼저 시작)
    other = ready_user(sent_codes, db, admin, "c2@hufs.ac.kr", gender="FEMALE")
    _goal(other, "CASUAL")
    assert nogoal.post("/api/v1/likes", json={"profile_id": other.profile_id}).status_code == 200
    assert other.post("/api/v1/likes", json={"profile_id": nogoal.profile_id}).json()["matched"] is True
    assert nogoal.post("/api/v1/likes", json={"profile_id": casual.profile_id}).status_code == 200

    data = admin.get("/api/v1/admin/watchlist?sort=likes").json()
    rows = {t["relationship_goal"] or "NONE": t for t in data["targets"]}
    assert rows["FRIEND"]["casual_matches"] == 1 and rows["FRIEND"]["casual_matches_started"] == 0
    assert rows["FRIEND"]["casual_likes"] == 1
    assert rows["NONE"]["casual_matches"] == 1 and rows["NONE"]["casual_matches_started"] == 1
    assert rows["NONE"]["casual_likes"] == 2 and rows["NONE"]["casual_liked_people"] == 2
    assert data["targets"][0]["relationship_goal"] is None  # 좋아요 많은 순
    assert data["totals"]["casual_matches"] == 2

    d = admin.get(f"/api/v1/admin/watchlist/{rows['FRIEND']['user_id']}").json()
    assert len(d["casual_matches"]) == 1
    m = d["casual_matches"][0]
    assert m["started"] == "them" and m["how"] == "서로 좋아요" and m["partner"]["relationship_goal"] == "CASUAL"
    assert d["casual_likes"][0]["count"] == 1


def test_import_from_casual_match_file(sent_codes, db, monkeypatch):
    """캐주얼 매칭 파일의 회원코드로 감시 대상에 한꺼번에 올린다 (이미 있는 사람은 그대로)."""
    admin, casual, friend, serious, nogoal = _setup(sent_codes, db)
    assert casual.post("/api/v1/likes", json={"profile_id": friend.profile_id}).status_code == 200
    assert friend.post("/api/v1/likes", json={"profile_id": casual.profile_id}).json()["matched"] is True
    db.query(WatchEvent).delete()
    db.query(WatchTarget).delete()
    db.commit()

    root = Path(__file__).resolve().parents[2] / "deploy"
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stderr", err)
    runpy.run_path(str(root / "casual_match_export.py"), run_name="__main__")
    csv_text = out.getvalue()

    for expected in ("새로 1명", "이미 있음 1명"):
        out = io.StringIO()
        monkeypatch.setattr(sys, "stdout", out)
        monkeypatch.setattr(sys, "stdin", io.StringIO(csv_text))
        runpy.run_path(str(root / "watch_import.py"), run_name="__main__")
        assert expected in out.getvalue(), out.getvalue()

    data = admin.get("/api/v1/admin/watchlist").json()
    assert len(data["targets"]) == 1
    t = data["targets"][0]
    assert t["origin"] == "MATCH_IMPORT" and t["relationship_goal"] == "FRIEND" and t["casual_matches"] == 1
