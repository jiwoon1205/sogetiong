"""한 번만 보여주는 공지 팝업 (2026-10-05).

- /me에 아직 안 본 공지 이름이 나온다.
- "확인"을 누르면 그 계정에는 다시 안 나온다 (다른 기기에서 로그인해도).
- 지금 공지가 아닌 이름은 받지 않는다. 공지를 끄면(None) 아무것도 안 나온다.
"""

from app.services import announcement_service

from tests.conftest import UserClient, signup


def test_shown_once_per_account(sent_codes, db):
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    key = announcement_service.CURRENT
    assert a.get("/api/v1/me").json()["announcement"] == key

    assert a.post("/api/v1/me/announcement/seen", json={"key": "old-one"}).status_code == 404
    r = a.post("/api/v1/me/announcement/seen", json={"key": key})
    assert r.status_code == 200
    assert a.get("/api/v1/me").json()["announcement"] is None

    # 다른 기기(새 로그인)에서도 다시 안 뜬다
    other = UserClient()
    assert other.post("/api/v1/auth/login", json={"email": "a@hufs.ac.kr", "password": "goodpass123"}).status_code == 200
    assert other.get("/api/v1/me").json()["announcement"] is None


def test_new_announcement_shows_again_and_can_be_off(sent_codes, db, monkeypatch):
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    a.post("/api/v1/me/announcement/seen", json={"key": announcement_service.CURRENT})
    monkeypatch.setattr(announcement_service, "CURRENT", "next-notice")
    assert a.get("/api/v1/me").json()["announcement"] == "next-notice"
    monkeypatch.setattr(announcement_service, "CURRENT", None)
    assert a.get("/api/v1/me").json()["announcement"] is None
