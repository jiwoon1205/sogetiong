"""대화방 ＋ 버튼: 사진 보내기 · 인스타 아이디 교환 (2026-11-14).

사진
- 1회 보기(ONCE): 받은 사람만, 딱 한 번 열린다. 보낸 사람도 다시 못 본다. 연 사진에는 보는 사람 코드가 새겨진다
- 대화에 보관(KEEP): 두 사람 모두 계속 볼 수 있다
- 관리자는 1회 보기 사진도 볼 수 있다 (90일 보관). 90일이 지나면 파일을 지운다 (처리 중 신고가 있으면 보관)
- 대화가 끝나면 보내지도, 보지도 못한다

인스타 아이디 교환
- 요청자·수락자 모두 아이디를 적고 "영구정지 안내"에 동의해야 한다
- 수락 전에는 요청자 아이디가 상대에게 안 보이고, 수락하면 두 아이디가 동시에 보인다
- 진행 중 요청은 하나, 교환 뒤엔 다시 요청 불가, 거절되면 24시간 뒤 다시 요청
- 관리자는 두 아이디를 볼 수 있다. 신고 사유 FAKE_INSTA_ID
"""

from datetime import timedelta
from io import BytesIO

from PIL import Image

from app.core.time import utcnow
from app.models.chat_extra import ChatPhoto, InstaShare
from app.models.matching import Report
from app.services import chat_extra_service
from app.services.storage_service import get_storage
from tests.conftest import admin_login, ready_user


def _pair(sent_codes, db):
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr", gender="FEMALE", prefs={"preferred_gender": "MALE"})
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr", gender="MALE", prefs={"preferred_gender": "FEMALE"})
    a.post("/api/v1/likes", json={"profile_id": b.profile_id})
    match_id = b.post("/api/v1/likes", json={"profile_id": a.profile_id}).json()["match_id"]
    return admin, a, b, match_id


def _jpeg(color=(30, 140, 200), size=(320, 240)) -> bytes:
    out = BytesIO()
    Image.new("RGB", size, color).save(out, format="JPEG")
    return out.getvalue()


def _send_photo(client, match_id, mode):
    return client.post(
        f"/api/v1/matches/{match_id}/photos",
        files={"file": ("x.jpg", _jpeg(), "image/jpeg")},
        data={"mode": mode},
    )


def _messages(client, match_id):
    r = client.get(f"/api/v1/matches/{match_id}/messages")
    assert r.status_code == 200, r.text
    return r.json()


# ---------- 사진 ----------

def test_once_photo_opens_only_once_for_receiver(sent_codes, db):
    _admin, a, b, match_id = _pair(sent_codes, db)
    r = _send_photo(a, match_id, "ONCE")
    assert r.status_code == 201, r.text
    sent = r.json()
    assert sent["type"] == "PHOTO" and sent["photo"]["mode"] == "ONCE"
    assert sent["photo"]["state"] == "SENT_UNOPENED" and "image_url" not in sent["photo"]
    photo_id = sent["photo"]["photo_id"]

    # 받은 사람 화면: 아직 안 봄, 주소 없음 (영구 주소를 주지 않는다)
    msg = _messages(b, match_id)["messages"][-1]
    assert msg["photo"]["state"] == "UNOPENED" and "image_url" not in msg["photo"]
    assert _messages(b, match_id)["once_seconds"] == 5

    # 보낸 사람은 못 연다
    assert a.post(f"/api/v1/matches/{match_id}/photos/{photo_id}/open").status_code == 403
    # 1회 보기 사진은 일반 주소로도 못 본다
    assert b.get(f"/api/v1/matches/{match_id}/photos/{photo_id}/image").status_code == 409

    opened = b.post(f"/api/v1/matches/{match_id}/photos/{photo_id}/open")
    assert opened.status_code == 200, opened.text
    assert opened.headers["content-type"] == "image/jpeg"
    assert "no-store" in opened.headers["cache-control"]
    with Image.open(BytesIO(opened.content)) as img:
        assert img.size == (320, 240)
    # 원본과 다르다 (보는 사람 코드가 새겨짐)
    assert opened.content != get_storage().read(db.query(ChatPhoto).one().storage_key)

    # 두 번째는 안 열린다
    again = b.post(f"/api/v1/matches/{match_id}/photos/{photo_id}/open")
    assert again.status_code == 410
    assert _messages(b, match_id)["messages"][-1]["photo"]["state"] == "OPENED"
    # 보낸 사람 화면: 상대가 봤어요 (예전 메시지도 extras로 상태가 바뀐다)
    extras = _messages(a, match_id)["extras"]["photos"]
    assert list(extras.values())[0]["state"] == "SENT_OPENED"
    # 파일은 관리자용으로 남아 있다
    assert db.query(ChatPhoto).one().storage_key != ""


def test_keep_photo_viewable_by_both(sent_codes, db):
    _admin, a, b, match_id = _pair(sent_codes, db)
    sent = _send_photo(a, match_id, "KEEP").json()
    assert sent["photo"]["state"] == "AVAILABLE"
    url = sent["photo"]["image_url"]
    for client in (a, b):
        r = client.get(url)
        assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
        assert r.content == get_storage().read(db.query(ChatPhoto).one().storage_key)  # 보관 사진은 워터마크 없음
    # 1회 보기 열기로는 안 열린다
    assert b.post(url.replace("/image", "/open")).status_code == 409
    # 대화 목록 미리보기
    matches = b.get("/api/v1/matches").json()["matches"]
    assert matches[0]["last_message"]["body"] == "사진을 보냈어요"


def test_photo_validation_and_permissions(sent_codes, db):
    _admin, a, b, match_id = _pair(sent_codes, db)
    assert _send_photo(a, match_id, "FOREVER").status_code == 422
    bad = a.post(
        f"/api/v1/matches/{match_id}/photos", files={"file": ("x.jpg", b"not an image", "image/jpeg")}, data={"mode": "KEEP"}
    )
    assert bad.status_code == 400

    # 다른 사람(대화방 밖)은 사진을 못 본다
    admin = admin_login(db, email="admin2@test.com")
    c = ready_user(sent_codes, db, admin, "c@hufs.ac.kr", gender="MALE", prefs={"preferred_gender": "FEMALE"})
    photo = _send_photo(a, match_id, "KEEP").json()["photo"]
    assert c.get(photo["image_url"]).status_code == 404

    # 대화가 끝나면 보내지도 보지도 못한다
    assert b.delete(f"/api/v1/matches/{match_id}").status_code == 200
    assert a.get(photo["image_url"]).status_code == 403
    assert _send_photo(a, match_id, "KEEP").status_code == 403


def test_photo_counts_for_super_like_wait(sent_codes, db, monkeypatch):
    """슈퍼 라이크를 보낸 사람은 답장 전 메시지 1개 → 사진·인스타 요청도 한 개로 친다."""
    from app.models.matching import Match

    _admin, a, b, match_id = _pair(sent_codes, db)
    match = db.get(Match, __import__("uuid").UUID(match_id))
    match.super_like_by = match.user_a_id if match.user_a_id else None
    db.commit()
    sender = a if _messages(a, match_id)["super_like"] == "sent" else b
    receiver = b if sender is a else a
    assert _send_photo(sender, match_id, "KEEP").status_code == 201
    assert _send_photo(sender, match_id, "KEEP").json()["detail"] == "SUPER_LIKE_WAIT_REPLY"
    r = sender.post(f"/api/v1/matches/{match_id}/insta", json={"handle": "me_123", "agree": True})
    assert r.status_code == 409 and r.json()["detail"] == "SUPER_LIKE_WAIT_REPLY"
    # 상대가 사진으로 답장해도 풀린다
    assert _send_photo(receiver, match_id, "ONCE").status_code == 201
    assert _send_photo(sender, match_id, "KEEP").status_code == 201


def test_admin_sees_chat_photos_including_once(sent_codes, db):
    admin, a, b, match_id = _pair(sent_codes, db)
    once = _send_photo(a, match_id, "ONCE").json()["photo"]
    b.post(f"/api/v1/matches/{match_id}/photos/{once['photo_id']}/open")

    r = admin.get(f"/api/v1/admin/matches/{match_id}/messages")
    assert r.status_code == 200, r.text
    msg = r.json()["messages"][-1]
    assert msg["type"] == "PHOTO" and msg["photo"]["mode"] == "ONCE" and msg["photo"]["viewed_at"]
    img = admin.get(msg["photo"]["image_url"])
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg"
    # 일반 사용자는 관리자 주소로 못 본다
    assert a.get(msg["photo"]["image_url"]).status_code == 401
    # 모더레이터(chats:read)도 볼 수 있다
    mod = admin_login(db, role="MODERATOR", email="mod@test.com")
    assert mod.get(msg["photo"]["image_url"]).status_code == 200


def test_photos_purged_after_90_days_unless_reported(sent_codes, db):
    _admin, a, b, match_id = _pair(sent_codes, db)
    _send_photo(a, match_id, "KEEP")
    _send_photo(a, match_id, "ONCE")
    photos = db.query(ChatPhoto).all()
    keys = [p.storage_key for p in photos]

    later = utcnow() + timedelta(days=89)
    assert chat_extra_service.purge_expired_photos(db, now=later) == 0

    # 처리 중인 신고가 있으면 보관
    later = utcnow() + timedelta(days=91)
    b.post("/api/v1/reports", json={"match_id": match_id, "reason": "OBSCENE_CONTENT"})
    assert db.query(Report).count() == 1
    assert chat_extra_service.purge_expired_photos(db, now=later) == 0

    db.query(Report).update({"status": "RESOLVED"})
    db.commit()
    assert chat_extra_service.purge_expired_photos(db, now=later) == 2
    db.expire_all()
    assert all(p.storage_key == "" and p.purged_at for p in db.query(ChatPhoto))
    for key in keys:
        try:
            get_storage().read(key)
            raise AssertionError("파일이 남아 있음")
        except FileNotFoundError:
            pass
    states = {p["state"] for p in _messages(b, match_id)["extras"]["photos"].values()}
    assert states == {"EXPIRED"}


# ---------- 인스타 아이디 교환 ----------

def test_insta_exchange_reveals_both_only_after_accept(sent_codes, db):
    admin, a, b, match_id = _pair(sent_codes, db)
    # 동의 안 하면 못 보냄 / 형식이 틀리면 못 보냄
    assert a.post(f"/api/v1/matches/{match_id}/insta", json={"handle": "me_123"}).status_code == 422
    bad = a.post(f"/api/v1/matches/{match_id}/insta", json={"handle": "한글아이디", "agree": True})
    assert bad.status_code == 422 and "영문" in bad.json()["detail"]
    for wrong in ("ab..cd", "abc.", "a b", "x" * 31):
        assert a.post(f"/api/v1/matches/{match_id}/insta", json={"handle": wrong, "agree": True}).status_code == 422

    r = a.post(f"/api/v1/matches/{match_id}/insta", json={"handle": " @Hufs.Kim_01 ", "agree": True})
    assert r.status_code == 201, r.text
    card = r.json()
    assert card["type"] == "INSTA_REQUEST"
    assert card["insta"]["status"] == "PENDING" and card["insta"]["my_handle"] == "hufs.kim_01"
    share_id = card["insta"]["share_id"]

    # 받은 사람: 요청은 보이지만 아이디는 아직 안 보인다
    got = _messages(b, match_id)
    req = got["messages"][-1]
    assert req["type"] == "INSTA_REQUEST" and req["insta"]["requested_by_me"] is False
    assert req["insta"]["partner_handle"] is None and req["insta"]["my_handle"] is None
    assert "hufs.kim_01" not in str(got)

    # 진행 중인 요청이 있으면 또 못 보냄 (양쪽 다)
    assert b.post(f"/api/v1/matches/{match_id}/insta", json={"handle": "bb", "agree": True}).status_code == 409
    # 요청한 사람은 수락 못 함
    assert a.post(f"/api/v1/matches/{match_id}/insta/{share_id}/accept", json={"handle": "x", "agree": True}).status_code == 403
    # 수락도 동의·아이디가 있어야
    assert b.post(f"/api/v1/matches/{match_id}/insta/{share_id}/accept", json={"handle": "b_insta"}).status_code == 422

    ok = b.post(f"/api/v1/matches/{match_id}/insta/{share_id}/accept", json={"handle": "b_insta", "agree": True})
    assert ok.status_code == 200, ok.text
    assert ok.json()["type"] == "INSTA_RESULT" and ok.json()["body"] == "인스타 아이디를 교환했어요"

    a_view = _messages(a, match_id)["extras"]["insta"]
    b_view = _messages(b, match_id)["extras"]["insta"]
    (av,) = a_view.values()
    (bv,) = b_view.values()
    assert av["status"] == "ACCEPTED" and av["my_handle"] == "hufs.kim_01" and av["partner_handle"] == "b_insta"
    assert bv["my_handle"] == "b_insta" and bv["partner_handle"] == "hufs.kim_01"

    # 두 번 수락·다시 요청 안 됨
    assert b.post(f"/api/v1/matches/{match_id}/insta/{share_id}/accept", json={"handle": "b_insta", "agree": True}).status_code == 409
    again = a.post(f"/api/v1/matches/{match_id}/insta", json={"handle": "hufs.kim_01", "agree": True})
    assert again.status_code == 409 and "이미" in again.json()["detail"]

    # 다음에 적을 때 미리 채워 줄 내 아이디
    assert _messages(a, match_id)["my_insta_handle"] == "hufs.kim_01"
    assert _messages(b, match_id)["my_insta_handle"] == "b_insta"

    # 관리자는 두 아이디를 다 본다
    msgs = admin.get(f"/api/v1/admin/matches/{match_id}/messages").json()["messages"]
    insta = next(m["insta"] for m in msgs if m["type"] == "INSTA_REQUEST")
    assert insta["requester_handle"] == "hufs.kim_01" and insta["responder_handle"] == "b_insta"
    assert insta["status"] == "ACCEPTED"

    # 가짜 아이디 신고
    rep = b.post("/api/v1/reports", json={"match_id": match_id, "reason": "FAKE_INSTA_ID", "description": "없는 계정"})
    assert rep.status_code in (200, 201), rep.text


def test_insta_decline_waits_24h_and_cancel(sent_codes, db):
    _admin, a, b, match_id = _pair(sent_codes, db)
    share_id = a.post(f"/api/v1/matches/{match_id}/insta", json={"handle": "aa_1", "agree": True}).json()["insta"]["share_id"]
    r = b.post(f"/api/v1/matches/{match_id}/insta/{share_id}/decline")
    assert r.status_code == 200 and r.json()["body"] == "인스타 아이디 교환을 거절했어요"
    # 거절해도 요청자 아이디는 끝까지 안 보인다
    assert "aa_1" not in str(_messages(b, match_id))
    assert b.post(f"/api/v1/matches/{match_id}/insta/{share_id}/decline").status_code == 409

    # 24시간 안에는 같은 사람이 다시 요청 못 함 (상대는 요청 가능)
    again = a.post(f"/api/v1/matches/{match_id}/insta", json={"handle": "aa_1", "agree": True})
    assert again.status_code == 409 and "24시간" in again.json()["detail"]
    share = db.query(InstaShare).one()
    share.responded_at = utcnow() - timedelta(hours=25)
    db.commit()
    r = a.post(f"/api/v1/matches/{match_id}/insta", json={"handle": "aa_1", "agree": True})
    assert r.status_code == 201
    new_id = r.json()["insta"]["share_id"]

    # 받은 사람은 취소 못 함, 요청한 사람은 취소 가능
    assert b.post(f"/api/v1/matches/{match_id}/insta/{new_id}/cancel").status_code == 403
    r = a.post(f"/api/v1/matches/{match_id}/insta/{new_id}/cancel")
    assert r.status_code == 200 and r.json()["body"] == "인스타 아이디 교환 요청을 취소했어요"
    # 취소 뒤에는 수락 못 함
    assert b.post(f"/api/v1/matches/{match_id}/insta/{new_id}/accept", json={"handle": "bb", "agree": True}).status_code == 409


def test_insta_needs_active_match(sent_codes, db):
    _admin, a, b, match_id = _pair(sent_codes, db)
    share_id = a.post(f"/api/v1/matches/{match_id}/insta", json={"handle": "aa_1", "agree": True}).json()["insta"]["share_id"]
    b.post("/api/v1/blocks", json={"profile_id": a.profile_id})
    assert b.post(f"/api/v1/matches/{match_id}/insta/{share_id}/accept", json={"handle": "bb", "agree": True}).status_code in (403, 404)


def test_new_message_types_notify_partner(sent_codes, db):
    _admin, a, b, match_id = _pair(sent_codes, db)
    _send_photo(a, match_id, "KEEP")
    matches = b.get("/api/v1/matches").json()["matches"]
    assert matches[0]["unread_count"] == 1
    a.post(f"/api/v1/matches/{match_id}/insta", json={"handle": "aa_1", "agree": True})
    assert b.get("/api/v1/matches").json()["matches"][0]["unread_count"] == 2
    # 일반 메시지에도 type이 붙는다
    r = a.post(f"/api/v1/matches/{match_id}/messages", json={"body": "안녕"})
    assert r.json()["type"] == "TEXT"
