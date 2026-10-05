"""휴대폰 알림(웹 푸시) + 메일 대체 테스트 (2026-10-05).

규칙
- 새 메시지·새 매칭만 알린다. 알림 글에 닉네임·대화 내용이 없다.
- 휴대폰 알림은 메시지마다 (카톡·DM처럼). 메일로 대신 보낼 때만 같은 방 10분에 한 번.
- 방금 사이트를 쓰던 사람에게는 안 보낸다.
- 휴대폰 알림이 켜진 기기가 없거나 모두 실패하면 메일 (메일 알림을 끄면 아무것도 안 감).
- 로그아웃하면 그 기기의 알림 주소가 지워진다.
"""

import base64
import json
import os

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.core.config import get_settings
from app.models.push import PushSubscription
from app.scripts.make_vapid_keys import make_keys
from app.services import push_service

from tests.conftest import admin_login, ready_user

FCM = "https://fcm.googleapis.com/fcm/send/"


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def browser_keys():
    """브라우저가 만드는 것과 같은 열쇠 (p256dh = 공개 열쇠, auth = 16바이트 비밀)."""
    private = ec.generate_private_key(ec.SECP256R1())
    public = private.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    auth = os.urandom(16)
    return private, auth, {"p256dh": _b64(public), "auth": _b64(auth)}


def subscribe(client, name="device1"):
    _, _, keys = browser_keys()
    endpoint = FCM + name
    r = client.put("/api/v1/me/alerts/push", json={"endpoint": endpoint, "keys": keys})
    assert r.status_code == 200, r.text
    return endpoint


@pytest.fixture
def push_on(monkeypatch):
    public, private = make_keys()
    monkeypatch.setattr(get_settings(), "vapid_public_key", public)
    monkeypatch.setattr(get_settings(), "vapid_private_key", private)
    return public


@pytest.fixture
def sent(monkeypatch):
    """배달 회사로 보내는 대신 기록한다. box["status"]로 배달 회사의 대답을 바꿀 수 있다."""
    box = {"push": [], "mail": [], "status": 201}

    def fake_webpush(sub, payload):
        box["push"].append((sub.endpoint, payload))
        return box["status"]

    monkeypatch.setattr(push_service, "_webpush", fake_webpush)
    monkeypatch.setattr(
        "app.services.email_service.EmailService.send_new_message_notice",
        staticmethod(lambda email, match_id: box["mail"].append(("MESSAGE", email, str(match_id)))),
    )
    monkeypatch.setattr(
        "app.services.email_service.EmailService.send_new_match_notice",
        staticmethod(lambda email, match_id: box["mail"].append(("MATCH", email, str(match_id)))),
    )
    return box


def _pair(sent_codes, db):
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr", gender="FEMALE", prefs={"preferred_gender": "MALE"}, nickname="몰래닉네임")
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr", gender="MALE", prefs={"preferred_gender": "FEMALE"})
    return a, b


def _match(a, b):
    a.post("/api/v1/likes", json={"profile_id": b.profile_id})
    match_id = b.post("/api/v1/likes", json={"profile_id": a.profile_id}).json()["match_id"]
    assert match_id
    return match_id


def _away():
    """모두가 사이트를 닫았다고 치기 (최근 접속 기록·10분 기록 지우기)."""
    push_service.reset()


# ---------- 켜기·끄기 ----------

def test_push_not_ready_without_keys(sent_codes, db):
    a, _ = _pair(sent_codes, db)
    state = a.get("/api/v1/me/alerts").json()
    assert state["push_available"] is False and state["public_key"] is None and state["email_notify"] is True
    _, _, keys = browser_keys()
    r = a.put("/api/v1/me/alerts/push", json={"endpoint": FCM + "x", "keys": keys})
    assert r.status_code == 409


def test_subscribe_only_to_real_push_services(sent_codes, db, push_on):
    a, _ = _pair(sent_codes, db)
    assert a.get("/api/v1/me/alerts").json()["public_key"] == push_on
    _, _, keys = browser_keys()
    for bad in ("http://fcm.googleapis.com/x", "https://evil.example.com/x", "https://fcm.googleapis.com.evil.com/x",
                "https://127.0.0.1/x", "https://fcm.googleapis.com:8443/x"):
        r = a.put("/api/v1/me/alerts/push", json={"endpoint": bad, "keys": keys})
        assert r.status_code == 422, bad
    for ok in (FCM + "abc", "https://web.push.apple.com/QAbc", "https://updates.push.services.mozilla.com/wpush/v2/x"):
        assert a.put("/api/v1/me/alerts/push", json={"endpoint": ok, "keys": keys}).status_code == 200, ok
    assert a.get("/api/v1/me/alerts").json()["device_count"] == 3
    # 끄기
    r = a.delete("/api/v1/me/alerts/push", json={"endpoint": FCM + "abc"})
    assert r.status_code == 200 and r.json()["device_count"] == 2


def test_same_browser_moves_to_new_login(sent_codes, db, push_on):
    a, b = _pair(sent_codes, db)
    endpoint = subscribe(a)
    # 같은 브라우저에서 b가 로그인해 알림을 켬 → a 것이 아니라 b 것이 된다
    _, _, keys = browser_keys()
    assert b.put("/api/v1/me/alerts/push", json={"endpoint": endpoint, "keys": keys}).status_code == 200
    assert a.get("/api/v1/me/alerts").json()["device_count"] == 0
    assert b.get("/api/v1/me/alerts").json()["device_count"] == 1


def test_device_limit(sent_codes, db, push_on, monkeypatch):
    monkeypatch.setattr(get_settings(), "push_max_devices", 2)
    a, _ = _pair(sent_codes, db)
    for i in range(4):
        subscribe(a, f"d{i}")
    assert a.get("/api/v1/me/alerts").json()["device_count"] == 2


def test_logout_removes_this_device(sent_codes, db, push_on):
    a, _ = _pair(sent_codes, db)
    subscribe(a)
    assert a.post("/api/v1/auth/logout").status_code == 200
    db.expire_all()
    assert db.query(PushSubscription).count() == 0


# ---------- 보내기 ----------

def test_new_message_push_without_names_or_text(sent_codes, db, push_on, sent):
    a, b = _pair(sent_codes, db)
    match_id = _match(a, b)
    endpoint = subscribe(a)
    sent["push"].clear()
    sent["mail"].clear()
    _away()

    b.post(f"/api/v1/matches/{match_id}/messages", json={"body": "비밀 내용 안녕"})
    assert len(sent["push"]) == 1
    to, payload = sent["push"][0]
    assert to == endpoint
    assert payload == {"title": "훕팅", "body": "새 메시지가 왔어요", "url": f"/chat/{match_id}", "tag": f"message-{match_id}"}
    text = json.dumps(payload, ensure_ascii=False)
    assert "비밀 내용" not in text and "몰래닉네임" not in text and "user_b" not in text
    assert sent["mail"] == []  # 휴대폰으로 갔으면 메일은 안 감

    # 메시지가 연달아 와도 하나하나 알림 (카톡·DM처럼). 잠금화면에는 같은 tag라 한 줄로 묶인다
    b.post(f"/api/v1/matches/{match_id}/messages", json={"body": "또 보냄"})
    b.post(f"/api/v1/matches/{match_id}/messages", json={"body": "또또"})
    assert len(sent["push"]) == 3
    assert {p["tag"] for _, p in sent["push"]} == {f"message-{match_id}"}


def test_no_alert_while_using_site(sent_codes, db, push_on, sent):
    a, b = _pair(sent_codes, db)
    match_id = _match(a, b)
    subscribe(a)
    _away()
    sent["push"].clear()
    a.get("/api/v1/notifications/unread-count")  # a가 화면을 보고 있음 (20초마다 부름)
    b.post(f"/api/v1/matches/{match_id}/messages", json={"body": "안녕"})
    assert sent["push"] == [] and sent["mail"] == []


def test_email_when_no_device_and_can_turn_off(sent_codes, db, sent):
    a, b = _pair(sent_codes, db)
    match_id = _match(a, b)
    _away()
    sent["mail"].clear()
    b.post(f"/api/v1/matches/{match_id}/messages", json={"body": "안녕"})
    assert sent["mail"] == [("MESSAGE", "a@hufs.ac.kr", match_id)]
    # 메일은 같은 방 10분에 한 번만 (메일함이 넘치지 않게)
    b.post(f"/api/v1/matches/{match_id}/messages", json={"body": "또"})
    assert len(sent["mail"]) == 1

    # 메일 알림 끄기
    r = a.patch("/api/v1/me/alerts", json={"email_notify": False})
    assert r.status_code == 200 and r.json()["email_notify"] is False
    _away()
    b.post(f"/api/v1/matches/{match_id}/messages", json={"body": "안녕2"})
    assert len(sent["mail"]) == 1


def test_gone_device_is_removed_and_falls_back_to_email(sent_codes, db, push_on, sent):
    a, b = _pair(sent_codes, db)
    match_id = _match(a, b)
    subscribe(a)
    _away()
    sent["mail"].clear()
    sent["status"] = 410  # 사용자가 휴대폰에서 알림을 껐음
    b.post(f"/api/v1/matches/{match_id}/messages", json={"body": "안녕"})
    db.expire_all()
    assert db.query(PushSubscription).count() == 0
    assert sent["mail"] == [("MESSAGE", "a@hufs.ac.kr", match_id)]


def test_new_match_alerts_the_other_person(sent_codes, db, push_on, sent):
    a, b = _pair(sent_codes, db)
    subscribe(a)
    subscribe(b, "device-b")
    a.post("/api/v1/likes", json={"profile_id": b.profile_id})
    _away()  # a는 사이트를 닫음
    sent["push"].clear()
    match_id = b.post("/api/v1/likes", json={"profile_id": a.profile_id}).json()["match_id"]
    # b는 방금 LIKE를 누른 사람이라 화면에서 이미 봤다 → a에게만
    assert [(e, p["body"], p["url"]) for e, p in sent["push"]] == [(FCM + "device1", "새로운 매칭이 생겼어요", f"/chat/{match_id}")]


def test_hidden_match_sends_nothing(sent_codes, db, push_on, sent):
    """매칭 정지로 숨겨진 매칭은 알림도 없다 (본인이 정지 사실을 알 수 없게)."""
    admin = admin_login(db, email="boss@test.com")
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr", gender="FEMALE", prefs={"preferred_gender": "MALE"})
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr", gender="MALE", prefs={"preferred_gender": "FEMALE"})
    subscribe(a)
    users = admin.get("/api/v1/admin/users").json()["users"]
    b_id = next(u["user_id"] for u in users if u["nickname"] == "user_b")
    r = admin.patch(f"/api/v1/admin/users/{b_id}/match-suspension", json={"suspended": True, "reason": "테스트 정지"})
    assert r.status_code == 200, r.text
    a.post("/api/v1/likes", json={"profile_id": b.profile_id})
    _away()
    sent["push"].clear()
    sent["mail"].clear()
    b.post("/api/v1/likes", json={"profile_id": a.profile_id})
    assert sent["push"] == [] and sent["mail"] == []


def test_test_button(sent_codes, db, push_on, sent):
    a, _ = _pair(sent_codes, db)
    assert a.post("/api/v1/me/alerts/push/test").status_code == 409  # 이 기기에서 안 켬
    subscribe(a)
    r = a.post("/api/v1/me/alerts/push/test")
    assert r.status_code == 200 and r.json()["delivered"] == 1
    sent["status"] = 500
    assert a.post("/api/v1/me/alerts/push/test").status_code == 502


# ---------- 진짜 암호화까지 ----------

def test_real_encryption_round_trip(sent_codes, db, push_on, monkeypatch):
    """pywebpush로 실제 암호화해서 보내고, 브라우저 열쇠로 풀어 내용이 맞는지 확인 (네트워크는 가짜)."""
    import http_ece
    import requests

    captured = {}

    class FakeResponse:
        status_code = 201
        text = ""
        headers: dict = {}

    def fake_post(self, url, data=None, headers=None, timeout=None, **kw):
        captured.update(url=url, data=data, headers=headers)
        return FakeResponse()

    monkeypatch.setattr(requests.Session, "post", fake_post)
    monkeypatch.setattr(requests, "post", lambda url, **kw: fake_post(None, url, **kw))

    a, _ = _pair(sent_codes, db)
    private, auth, keys = browser_keys()
    endpoint = FCM + "real"
    assert a.put("/api/v1/me/alerts/push", json={"endpoint": endpoint, "keys": keys}).status_code == 200
    r = a.post("/api/v1/me/alerts/push/test")
    assert r.status_code == 200, r.text

    assert captured["url"] == endpoint
    assert captured["headers"]["Authorization"].startswith("vapid ")
    assert captured["headers"]["Urgency"] == "high"
    plain = http_ece.decrypt(captured["data"], private_key=private, auth_secret=auth, version="aes128gcm")
    assert json.loads(plain) == {"title": "훕팅", "body": "알림이 잘 켜졌어요", "url": "/settings#alerts", "tag": "test"}
