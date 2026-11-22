"""게시판(자유·연애·캐주얼)·쪽지·신고·이용 정지 (2026-11-22)."""

from app.models.board import BoardPost
from app.models.matching import Notification
from app.models.user import User
from app.services import push_service
from tests.conftest import admin_login, jpeg_with_exif, ready_user, signup


def _people(sent_codes, db, goals=(None, None)):
    admin = admin_login(db)
    w = ready_user(sent_codes, db, admin, "w@hufs.ac.kr", gender="FEMALE")
    m = ready_user(sent_codes, db, admin, "m@hufs.ac.kr", gender="MALE")
    for client, goal in ((w, goals[0]), (m, goals[1])):
        if goal:
            assert client.patch("/api/v1/me/profile", json={"relationship_goal": goal}).status_code == 200
    return admin, w, m


def _make(client, nickname, score=None):
    r = client.post("/api/v1/board/profile", json={"nickname": nickname, "shown_score": score})
    assert r.status_code == 201, r.text
    return r.json()


def _post(client, board="FREE", title="안녕", body="첫 글"):
    r = client.post("/api/v1/board/posts", json={"board": board, "title": title, "body": body})
    assert r.status_code == 201, r.text
    return r.json()


def _user(db, email):
    db.expire_all()
    return db.query(User).filter(User.email == email).one()


def test_board_needs_profile_and_approved_photo(sent_codes, db):
    admin, w, m = _people(sent_codes, db)
    # 사진 검수 전에는 못 만든다
    fresh = signup(sent_codes, db, "new@hufs.ac.kr")
    me = fresh.get("/api/v1/board/me").json()
    assert me["profile"] is None and me["can_create"] is False
    assert fresh.post("/api/v1/board/profile", json={"nickname": "새내기"}).status_code == 403
    # 프로필 없이는 게시판을 못 본다
    r = w.get("/api/v1/board/posts")
    assert r.status_code == 403 and r.json()["detail"]["code"] == "NO_BOARD_PROFILE"
    prof = _make(w, "봄바람", "style")
    assert prof["gender"] == "FEMALE" and prof["school"] and prof["score"]["value"] == 7
    # 닉네임 중복·30일 제한
    assert m.post("/api/v1/board/profile", json={"nickname": "봄바람"}).status_code == 409
    assert w.patch("/api/v1/board/profile", json={"nickname": "여름비"}).status_code == 409


def test_post_shows_only_board_profile(sent_codes, db):
    admin, w, m = _people(sent_codes, db)
    _make(w, "봄바람")
    _make(m, "가을")
    post = _post(w)
    listed = m.get("/api/v1/board/posts").json()["posts"]
    assert listed[0]["id"] == post["id"]
    author = listed[0]["author"]
    assert author["nickname"] == "봄바람" and author["score"] is None
    # 소개팅 닉네임은 어디에도 없다
    assert "user_w" not in str(listed)


def test_love_and_casual_boards_follow_relationship_goal(sent_codes, db):
    admin, w, m = _people(sent_codes, db, ("SERIOUS", "CASUAL"))
    _make(w, "진지")
    _make(m, "캐주얼")
    boards = {b["key"]: b["allowed"] for b in w.get("/api/v1/board/me").json()["boards"]}
    assert boards == {"FREE": True, "LOVE": True, "CASUAL": False}
    love = _post(w, "LOVE")
    casual = _post(m, "CASUAL")
    # 서로 남의 게시판은 못 보고 못 쓴다
    assert m.get("/api/v1/board/posts?board=LOVE").status_code == 403
    assert w.get("/api/v1/board/posts?board=CASUAL").status_code == 403
    assert m.get(f"/api/v1/board/posts/{love['id']}").status_code == 403
    assert w.post(f"/api/v1/board/posts/{casual['id']}/comments", json={"body": "hi"}).status_code == 403
    r = w.post("/api/v1/board/posts", json={"board": "CASUAL", "title": "a", "body": "b"})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "BOARD_NOT_ALLOWED"
    # 자유 게시판엔 둘 다
    assert m.get("/api/v1/board/posts?board=FREE").status_code == 200
    # 캐주얼 게시판 밖에는 성적인 이야기 금지 안내
    rules = {b["key"]: b["sexual_rule"] for b in w.get("/api/v1/board/me").json()["boards"]}
    assert rules["CASUAL"] is None and rules["FREE"]


def test_comment_notifies_author(sent_codes, db):
    admin, w, m = _people(sent_codes, db)
    _make(w, "봄바람")
    _make(m, "가을")
    post = _post(w)
    r = m.post(f"/api/v1/board/posts/{post['id']}/comments", json={"body": "반가워요"})
    assert r.status_code == 201
    detail = w.get(f"/api/v1/board/posts/{post['id']}").json()
    assert detail["post"]["comment_count"] == 1 and detail["comments"][0]["body"] == "반가워요"
    wid = _user(db, "w@hufs.ac.kr").id
    assert db.query(Notification).filter(Notification.user_id == wid, Notification.type == "BOARD_COMMENT").count() == 1


def test_three_reports_hide_post_and_admin_can_delete(sent_codes, db):
    admin, w, m = _people(sent_codes, db)
    _make(w, "글쓴이")
    _make(m, "신고1")
    post = _post(w)
    reporters = [m]
    for i in range(2):
        c = ready_user(sent_codes, db, admin, f"r{i}@hufs.ac.kr")
        _make(c, f"신고{i + 2}")
        reporters.append(c)
    for c in reporters:
        r = c.post("/api/v1/board/reports", json={"target_type": "POST", "target_id": post["id"], "reason": "SEXUAL"})
        assert r.status_code == 201, r.text
    # 같은 사람이 또 신고는 안 됨
    assert m.post("/api/v1/board/reports", json={"target_type": "POST", "target_id": post["id"], "reason": "SPAM"}).status_code == 409
    assert m.get("/api/v1/board/posts").json()["posts"] == []
    reports = admin.get("/api/v1/admin/board/reports").json()["reports"]
    assert len(reports) == 3 and reports[0]["reason_label"] == "성적인 이야기"
    # 관리자가 숨김 풀기 → 다시 보임 → 즉시 삭제
    assert admin.post(f"/api/v1/admin/board/posts/{post['id']}/unhide").status_code == 200
    assert len(m.get("/api/v1/board/posts").json()["posts"]) == 1
    assert admin.delete(f"/api/v1/admin/board/posts/{post['id']}").status_code == 200
    assert m.get("/api/v1/board/posts").json()["posts"] == []


def test_ban_blocks_writing_and_notifies(sent_codes, db):
    admin, w, m = _people(sent_codes, db)
    prof = _make(m, "말썽")
    r = admin.post(f"/api/v1/admin/board/profiles/{prof['id']}/ban", json={"days": 7, "reason": "자유 게시판에서 성적인 이야기"})
    assert r.status_code == 200, r.text
    mid = _user(db, "m@hufs.ac.kr").id
    notes = db.query(Notification).filter(Notification.user_id == mid, Notification.type == "BOARD_BAN").all()
    assert len(notes) == 1 and "7일" in notes[0].body
    r = m.post("/api/v1/board/posts", json={"board": "FREE", "title": "a", "body": "b"})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "BOARD_BANNED"
    me = m.get("/api/v1/board/me").json()["profile"]
    assert me["banned_until"] and me["ban_reason"]
    # 읽기는 된다
    assert m.get("/api/v1/board/posts").status_code == 200
    assert admin.post(f"/api/v1/admin/board/profiles/{prof['id']}/unban").status_code == 200
    _post(m)
    # 영구 정지
    r = admin.post(f"/api/v1/admin/board/profiles/{prof['id']}/ban", json={"days": None, "reason": "반복 위반"})
    assert r.json()["ban_permanent"] is True


def test_ban_push_payload():
    import uuid
    alert = push_service.Alert(user_id=uuid.uuid4(), kind=push_service.BOARD_BAN, match_id=uuid.uuid4())
    assert push_service.payload_for(alert)["url"] == "/board"
    alert = push_service.Alert(user_id=uuid.uuid4(), kind=push_service.NOTE, match_id=alert.match_id)
    assert push_service.payload_for(alert)["url"] == f"/notes/{alert.match_id}"


def test_note_costs_super_like_and_waits_for_reply(sent_codes, db):
    admin, w, m = _people(sent_codes, db)
    wp = _make(w, "봄바람")
    _make(m, "가을")
    # 남성: 슈퍼 라이크 없으면 못 보냄
    r = m.post("/api/v1/notes", json={"board_profile_id": wp["id"], "body": "안녕하세요"})
    assert r.status_code == 402
    user = _user(db, "m@hufs.ac.kr")
    user.super_likes = 1
    db.commit()
    r = m.post("/api/v1/notes", json={"board_profile_id": wp["id"], "body": "안녕하세요"})
    assert r.status_code == 201 and r.json()["new"] is True
    room = r.json()["room"]["id"]
    assert _user(db, "m@hufs.ac.kr").super_likes == 0
    # 답장 전엔 1개만
    assert m.post(f"/api/v1/notes/{room}/messages", json={"body": "또"}).status_code == 409
    # 다시 열어도 같은 방, 돈 안 씀
    r = m.post("/api/v1/notes", json={"board_profile_id": wp["id"], "body": "x"})
    assert r.json()["new"] is False and r.json()["room"]["id"] == room
    # 받은 사람 목록·읽음
    rooms = w.get("/api/v1/notes").json()["rooms"]
    assert rooms[0]["unread"] == 1 and rooms[0]["partner"]["nickname"] == "가을"
    assert w.post(f"/api/v1/notes/{room}/messages", json={"body": "반가워요"}).status_code == 201
    assert m.post(f"/api/v1/notes/{room}/messages", json={"body": "저도요"}).status_code == 201
    # 나가면 끝
    assert w.post(f"/api/v1/notes/{room}/leave").status_code == 200
    assert m.post(f"/api/v1/notes/{room}/messages", json={"body": "?"}).status_code == 409


def test_women_get_three_free_notes(sent_codes, db, monkeypatch):
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "female_free", True)
    admin, w, m = _people(sent_codes, db)
    _make(w, "봄바람")
    targets = [_make(m, "가을")]
    for i in range(3):
        c = ready_user(sent_codes, db, admin, f"x{i}@hufs.ac.kr", gender="MALE")
        targets.append(_make(c, f"남{i}"))
    for t in targets[:3]:
        assert w.post("/api/v1/notes", json={"board_profile_id": t["id"], "body": "hi"}).status_code == 201
    assert w.get("/api/v1/board/me").json()["free_notes_left"] == 0
    assert w.post("/api/v1/notes", json={"board_profile_id": targets[3]["id"], "body": "hi"}).status_code == 402


def test_block_hides_posts_and_closes_notes(sent_codes, db):
    admin, w, m = _people(sent_codes, db)
    wp = _make(w, "봄바람")
    mp = _make(m, "가을")
    _post(m)
    user = _user(db, "w@hufs.ac.kr")
    user.super_likes = 1
    db.commit()
    assert w.post("/api/v1/notes", json={"board_profile_id": mp["id"], "body": "hi"}).status_code == 201
    assert w.post("/api/v1/board/blocks", json={"board_profile_id": mp["id"]}).status_code == 201
    assert w.get("/api/v1/board/posts").json()["posts"] == []
    assert w.get("/api/v1/notes").json()["rooms"] == []
    assert m.post("/api/v1/notes", json={"board_profile_id": wp["id"], "body": "hi"}).status_code == 403


def test_avatar_upload_and_reset(sent_codes, db):
    admin, w, m = _people(sent_codes, db)
    wp = _make(w, "봄바람")
    _make(m, "가을")
    r = w.post("/api/v1/board/profile/avatar", files={"file": ("a.jpg", jpeg_with_exif(), "image/jpeg")})
    assert r.status_code == 200 and r.json()["has_avatar"] is True
    assert m.get(f"/api/v1/board/avatars/{wp['id']}").status_code == 200
    assert admin.post(f"/api/v1/admin/board/profiles/{wp['id']}/reset-avatar").status_code == 200
    assert m.get(f"/api/v1/board/avatars/{wp['id']}").status_code == 404


def test_withdrawn_author_shows_as_deleted(sent_codes, db):
    from app.services import withdrawal_service
    admin, w, m = _people(sent_codes, db)
    _make(w, "봄바람")
    _make(m, "가을")
    _post(w)
    user = _user(db, "w@hufs.ac.kr")
    from app.core.time import utcnow
    user.deleted_at = utcnow()
    user.status = "DELETED"
    withdrawal_service.purge_user_data(db, user.id)
    db.commit()
    posts = m.get("/api/v1/board/posts").json()["posts"]
    assert posts[0]["author"]["nickname"] == "탈퇴한 사용자"
    assert db.query(BoardPost).count() == 1


def test_men_without_membership_can_use_board(sent_codes, db, monkeypatch):
    """게시판은 사진 검수를 받은 모든 회원이 쓸 수 있다 (이용권 없는 남성도, 2026-11-22)."""
    from app.core.config import get_settings
    admin, w, m = _people(sent_codes, db)
    s = get_settings()
    monkeypatch.setattr(s, "membership_enabled", True)
    monkeypatch.setattr(s, "vip_enabled", True)
    monkeypatch.setattr(s, "vip_test_emails", "")
    assert m.get("/api/v1/board/me").json()["can_create"] is True
    _make(m, "이용권없음")
    post = _post(m)
    _make(w, "봄바람")
    assert w.post(f"/api/v1/board/posts/{post['id']}/comments", json={"body": "hi"}).status_code == 201
    assert m.post(f"/api/v1/board/posts/{post['id']}/comments", json={"body": "고마워요"}).status_code == 201


def test_reply_to_reply_stays_under_top_comment(sent_codes, db):
    """답글에 답글 (2026-11-22): 모두 맨 위 댓글 밑에 붙고, 누구에게 단 답글인지 보인다. 답글 받은 사람에게 알림."""
    admin, w, m = _people(sent_codes, db)
    _make(w, "글쓴이")
    _make(m, "가을")
    third = ready_user(sent_codes, db, admin, "t@hufs.ac.kr")
    _make(third, "나무")
    post = _post(w)
    url = f"/api/v1/board/posts/{post['id']}/comments"
    top = m.post(url, json={"body": "첫 댓글"}).json()
    r1 = third.post(url, json={"body": "답글", "reply_to_id": top["id"]})
    assert r1.status_code == 201 and r1.json()["parent_id"] == top["id"] and r1.json()["reply_to"] == "가을"
    r2 = m.post(url, json={"body": "답글의 답글", "reply_to_id": r1.json()["id"]})
    assert r2.status_code == 201 and r2.json()["parent_id"] == top["id"] and r2.json()["reply_to"] == "나무"
    # 다른 글의 댓글에는 답글 못 닮
    other = _post(w, title="다른 글")
    bad = m.post(f"/api/v1/board/posts/{other['id']}/comments", json={"body": "x", "reply_to_id": top["id"]})
    assert bad.status_code == 404
    comments = w.get(f"/api/v1/board/posts/{post['id']}").json()["comments"]
    assert [c["parent_id"] for c in comments] == [None, top["id"], top["id"]]
    assert w.get(f"/api/v1/board/posts/{post['id']}").json()["post"]["comment_count"] == 3
    # 알림: 가을(첫 댓글 → 나무가 답글), 나무(가을이 답글)
    for email in ("m@hufs.ac.kr", "t@hufs.ac.kr"):
        uid = _user(db, email).id
        assert db.query(Notification).filter(Notification.user_id == uid, Notification.title == "내 댓글에 답글이 달렸어요").count() == 1


def test_admin_can_list_and_read_note_rooms(sent_codes, db):
    """관리자는 신고 없이도 쪽지방 목록을 보고 내용을 열 수 있다 (열면 감사 로그)."""
    from app.models.admin import AuditLog
    admin, w, m = _people(sent_codes, db)
    _make(w, "봄바람")
    mp = _make(m, "가을")
    room = w.post("/api/v1/notes", json={"board_profile_id": mp["id"], "body": "안녕하세요"})
    if room.status_code == 402:
        user = _user(db, "w@hufs.ac.kr")
        user.super_likes = 1
        db.commit()
        room = w.post("/api/v1/notes", json={"board_profile_id": mp["id"], "body": "안녕하세요"})
    room_id = room.json()["room"]["id"]
    rooms = admin.get("/api/v1/admin/board/notes").json()["rooms"]
    assert rooms[0]["id"] == room_id and rooms[0]["messages"] == 1 and "안녕하세요" not in str(rooms)
    assert rooms[0]["starter"]["nickname"] == "봄바람" and rooms[0]["receiver"]["nickname"] == "가을"
    detail = admin.get(f"/api/v1/admin/board/notes/{room_id}").json()
    assert detail["messages"][0]["body"] == "안녕하세요"
    assert db.query(AuditLog).filter(AuditLog.action == "NOTE_VIEW").count() == 1
    activity = admin.get(f"/api/v1/admin/board/profiles/{mp['id']}").json()
    assert activity["notes"][0]["id"] == room_id
