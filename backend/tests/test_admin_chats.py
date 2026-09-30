"""관리자 대화 열람 테스트.

정책: chats:read 권한(SUPER_ADMIN, MODERATOR)이 있으면 신고 여부와 상관없이 모든 대화를 볼 수 있다.
전체 대화 목록(/admin/matches)에서 바로 찾아 열 수 있다.
열 때마다 감사 로그(CHAT_VIEW)가 남는다.
"""

from app.core.config import Settings
from app.models.admin import AuditLog

from tests.conftest import UserClient, admin_login, ready_user


def _matched_pair(sent_codes, db, admin):
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr", gender="FEMALE", prefs={"preferred_gender": "MALE"})
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr", gender="MALE", prefs={"preferred_gender": "FEMALE"})
    a.post("/api/v1/likes", json={"profile_id": b.profile_id})
    match_id = b.post("/api/v1/likes", json={"profile_id": a.profile_id}).json()["match_id"]
    a.post(f"/api/v1/matches/{match_id}/messages", json={"body": "안녕하세요"})
    b.post(f"/api/v1/matches/{match_id}/messages", json={"body": "반가워요 :)"})
    return a, b, match_id


def _user_id(admin, nickname_part):
    users = admin.get("/api/v1/admin/users").json()["users"]
    return next(u["user_id"] for u in users if u["nickname"] and nickname_part in u["nickname"])


def test_moderator_can_read_any_chat_and_it_is_audited(sent_codes, db):
    super_admin = admin_login(db)
    a, b, match_id = _matched_pair(sent_codes, db, super_admin)
    moderator = admin_login(db, role="MODERATOR")

    # 사용자별 대화 목록 (신고가 없어도 볼 수 있음)
    a_id = _user_id(moderator, "user_a")
    matches = moderator.get(f"/api/v1/admin/users/{a_id}/matches").json()["matches"]
    assert len(matches) == 1 and matches[0]["match_id"] == match_id
    assert matches[0]["message_count"] == 2

    r = moderator.get(f"/api/v1/admin/matches/{match_id}/messages")
    assert r.status_code == 200, r.text
    bodies = [m["body"] for m in r.json()["messages"]]
    assert bodies == ["안녕하세요", "반가워요 :)"]
    assert "a@hufs.ac.kr" not in r.text  # 이메일은 없다

    db.expire_all()
    logs = db.query(AuditLog).filter(AuditLog.action == "CHAT_VIEW").all()
    assert len(logs) == 1 and str(logs[0].target_id) == match_id


def test_ended_chat_is_still_readable(sent_codes, db):
    admin = admin_login(db)
    a, b, match_id = _matched_pair(sent_codes, db, admin)
    assert a.delete(f"/api/v1/matches/{match_id}").status_code == 200  # 매칭 해제
    r = admin.get(f"/api/v1/admin/matches/{match_id}/messages")
    assert r.status_code == 200
    assert r.json()["status"] == "UNMATCHED" and len(r.json()["messages"]) == 2


def test_photo_reviewer_and_users_cannot_read_chats(sent_codes, db):
    admin = admin_login(db)
    a, b, match_id = _matched_pair(sent_codes, db, admin)
    reviewer = admin_login(db, role="PHOTO_REVIEWER")
    assert reviewer.get(f"/api/v1/admin/matches/{match_id}/messages").status_code == 403
    # 일반 사용자 (대화 당사자여도 관리자 API는 불가)
    assert a.get(f"/api/v1/admin/matches/{match_id}/messages").status_code == 401
    assert UserClient().get(f"/api/v1/admin/matches/{match_id}/messages").status_code == 401


def test_paging_older_messages(sent_codes, db):
    admin = admin_login(db)
    a, b, match_id = _matched_pair(sent_codes, db, admin)
    for i in range(5):
        a.post(f"/api/v1/matches/{match_id}/messages", json={"body": f"메시지 {i}"})
    first = admin.get(f"/api/v1/admin/matches/{match_id}/messages?limit=3").json()
    assert first["has_more"] is True and [m["body"] for m in first["messages"]] == ["메시지 2", "메시지 3", "메시지 4"]
    older = admin.get(f"/api/v1/admin/matches/{match_id}/messages?limit=3&before={first['messages'][0]['message_id']}").json()
    assert [m["body"] for m in older["messages"]] == ["반가워요 :)", "메시지 0", "메시지 1"]


def test_all_chats_list_shows_unreported_chats(sent_codes, db):
    """신고가 없는 대화방도 전체 대화 목록에 나오고, 바로 열 수 있다."""
    admin = admin_login(db)
    a, b, match_id = _matched_pair(sent_codes, db, admin)
    moderator = admin_login(db, role="MODERATOR")

    r = moderator.get("/api/v1/admin/matches")
    assert r.status_code == 200, r.text
    rows = r.json()["matches"]
    assert [m["match_id"] for m in rows] == [match_id]
    assert rows[0]["message_count"] == 2 and rows[0]["status"] == "ACTIVE"
    assert len(rows[0]["members"]) == 2 and all(p["nickname"] for p in rows[0]["members"])
    assert "안녕하세요" not in r.text  # 목록에는 메시지 내용이 없다
    assert r.json()["has_more"] is False

    # 목록만 보는 것은 감사 로그를 남기지 않는다
    db.expire_all()
    assert db.query(AuditLog).filter(AuditLog.action == "CHAT_VIEW").count() == 0

    # 끝난 대화도 목록에 남는다 + 상태 필터
    a.delete(f"/api/v1/matches/{match_id}")
    assert moderator.get("/api/v1/admin/matches?status=ACTIVE").json()["matches"] == []
    ended = moderator.get("/api/v1/admin/matches?status=UNMATCHED").json()["matches"]
    assert [m["match_id"] for m in ended] == [match_id]

    # 닉네임 검색 (둘 중 한 명의 닉네임이면 나온다)
    nick = rows[0]["members"][0]["nickname"]
    assert len(moderator.get(f"/api/v1/admin/matches?nickname={nick}").json()["matches"]) == 1
    assert moderator.get("/api/v1/admin/matches?nickname=없는닉네임").json()["matches"] == []


def test_all_chats_list_permissions(sent_codes, db):
    admin = admin_login(db)
    a, b, match_id = _matched_pair(sent_codes, db, admin)
    reviewer = admin_login(db, role="PHOTO_REVIEWER")
    assert reviewer.get("/api/v1/admin/matches").status_code == 403
    assert a.get("/api/v1/admin/matches").status_code == 401


def test_all_chats_list_paging(sent_codes, db):
    admin = admin_login(db)
    _matched_pair(sent_codes, db, admin)
    first = admin.get("/api/v1/admin/matches?limit=1").json()
    assert len(first["matches"]) == 1 and first["has_more"] is False
    assert admin.get("/api/v1/admin/matches?offset=1").json()["matches"] == []


def test_prod_rejects_public_example_secret_key():
    base = dict(
        APP_ENV="prod",
        database_url="postgresql+psycopg://x/y",
        email_backend="smtp",
        cookie_secure=True,
        cors_origins="https://example.com",
    )
    for public in ("replace-with-a-long-random-secret", "change-me-in-production"):
        try:
            Settings(secret_key=public, **base).validate_settings()
        except ValueError as exc:
            assert "SECRET_KEY" in str(exc)
        else:
            raise AssertionError("예시 SECRET_KEY가 운영 검사를 통과하면 안 된다")
