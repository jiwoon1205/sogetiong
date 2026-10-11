"""슈퍼 라이크 (2026-10-12)."""

from app.models.admin import AuditLog
from app.models.matching import Match
from tests.conftest import admin_login, discover_ids, ready_user
from tests.test_free_trial import like, women, world  # noqa: F401  (fixture)
from tests.test_membership import paid_world, user_of  # noqa: F401  (fixture)


def _give(admin, db, client, count):
    uid = user_of(db, client).id
    r = admin.post(f"/api/v1/admin/users/{uid}/super-likes", json={"count": count, "reason": "이벤트"})
    assert r.status_code == 200, r.text
    return uid


def _super(client, other):
    return client.post("/api/v1/super-likes", json={"profile_id": other.profile_id})


def _buy(admin, client, quantity):
    r = client.get("/api/v1/me/super-likes", params={"quantity": quantity})
    assert r.status_code == 200 and r.json()["can_buy"], r.text
    assert r.json()["payment"]["amount"] == quantity * 1000 and r.json()["payment"]["quantity"] == quantity
    r = client.post("/api/v1/me/super-likes/request", params={"quantity": quantity})
    assert r.status_code == 200, r.text
    pay = next(p for p in admin.get("/api/v1/admin/payments").json()["payments"] if p["kind"] == "SUPER_LIKE")
    assert pay["quantity"] == quantity and pay["amount"] == quantity * 1000
    assert admin.post(f"/api/v1/admin/payments/{pay['payment_id']}/confirm").status_code == 200
    return pay["payment_id"]


def test_super_like_forces_match_and_limits_messages(sent_codes, db, world):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    her = ready_user(sent_codes, db, admin, "her@hufs.ac.kr", gender="FEMALE", want="MALE")

    # 없으면 구매 안내
    r = _super(me, her)
    assert r.status_code == 409 and r.json()["detail"] == "SUPER_LIKE_REQUIRED"

    _give(admin, db, me, 2)
    assert me.get("/api/v1/discover").json()["super_likes"]["count"] == 2
    r = _super(me, her)
    assert r.status_code == 200 and r.json()["matched"] is True, r.text
    assert r.json()["super_likes"]["count"] == 1
    mid = r.json()["match_id"]

    # 받은 사람: 대화 목록·대화방에 "received", 알림 문구
    item = next(m for m in her.get("/api/v1/matches").json()["matches"] if m["match_id"] == mid)
    assert item["super_like"] == "received"
    notes = her.get("/api/v1/notifications").json()["notifications"]
    assert any(n["title"] == "슈퍼 라이크로 연결됐어요" for n in notes)

    # 보낸 사람은 답장 전까지 1개만
    url = f"/api/v1/matches/{mid}/messages"
    assert me.get(url).json()["send_locked"] is False
    assert me.post(url, json={"body": "안녕하세요"}).status_code == 201
    assert me.get(url).json()["send_locked"] is True
    r = me.post(url, json={"body": "또"})
    assert r.status_code == 409 and r.json()["detail"] == "SUPER_LIKE_WAIT_REPLY"
    # 받은 사람은 제한 없음, 답장하면 풀림
    assert her.get(url).json()["send_locked"] is False and her.get(url).json()["super_like"] == "received"
    assert her.post(url, json={"body": "반가워요"}).status_code == 201
    assert me.post(url, json={"body": "또 안녕"}).status_code == 201
    assert me.get(url).json()["send_locked"] is False

    # 좋아요 개수(여기서는 체험 3개)를 쓰지 않는다
    assert me.get("/api/v1/discover").json()["likes_left_today"] == 3


def test_super_like_only_to_recommendable_people(sent_codes, db, world):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    man = ready_user(sent_codes, db, admin, "man@hufs.ac.kr", gender="MALE", want="FEMALE")
    her = ready_user(sent_codes, db, admin, "her@hufs.ac.kr", gender="FEMALE", want="MALE")
    _give(admin, db, me, 3)
    assert _super(me, man).status_code == 404  # 성별 조건 밖
    assert her.post("/api/v1/blocks", json={"profile_id": me.profile_id}).status_code == 201
    assert _super(me, her).status_code == 404  # 차단
    assert user_of(db, me).super_likes == 3  # 실패하면 쓰지 않음


def test_hidden_match_when_suspended(sent_codes, db, world):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    her = ready_user(sent_codes, db, admin, "her@hufs.ac.kr", gender="FEMALE", want="MALE")
    uid = _give(admin, db, me, 1)
    assert admin.patch(f"/api/v1/admin/users/{uid}/match-suspension", json={"suspended": True, "reason": "테스트"}).status_code == 200
    r = _super(me, her)
    assert r.status_code == 200 and r.json()["matched"] is False
    assert db.query(Match).filter(Match.status == "HIDDEN").count() == 1
    assert her.get("/api/v1/matches").json()["matches"] == []


def test_buy_confirm_and_refund(sent_codes, db, world):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    her = ready_user(sent_codes, db, admin, "her@hufs.ac.kr", gender="FEMALE", want="MALE")
    pid = _buy(admin, me, 3)
    assert me.get("/api/v1/me").json()["super_likes"]["count"] == 3
    # 체험 이용자도 살 수 있고(이용권 없음), 쓰지 않았으면 환불 가능
    row = next(p for p in admin.get("/api/v1/admin/payments?view=history").json()["payments"] if p["payment_id"] == pid)
    assert row["refundable"] is True
    # 하나 쓰면 환불 불가
    assert _super(me, her).status_code == 200
    row = next(p for p in admin.get("/api/v1/admin/payments?view=history").json()["payments"] if p["payment_id"] == pid)
    assert row["refundable"] is False
    assert admin.post(f"/api/v1/admin/payments/{pid}/refund").status_code == 409

    # 새로 산 것을 안 쓰고 환불
    pid2 = _buy(admin, me, 2)
    assert admin.post(f"/api/v1/admin/payments/{pid2}/refund").status_code == 200
    assert me.get("/api/v1/me").json()["super_likes"]["count"] == 2
    # 이용권 혜택(재검토)은 생기지 않는다
    assert user_of(db, me).rereview_granted_at is None
    assert db.query(AuditLog).filter(AuditLog.action == "PAYMENT_REFUND").count() == 1


def test_quantity_is_clamped_and_fixed_after_request(sent_codes, db, world):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    assert me.get("/api/v1/me/super-likes", params={"quantity": 50}).json()["payment"]["quantity"] == 10
    assert me.post("/api/v1/me/super-likes/request", params={"quantity": 4}).json()["payment"]["amount"] == 4000
    # 누른 뒤에는 바뀌지 않는다
    assert me.get("/api/v1/me/super-likes", params={"quantity": 7}).json()["payment"]["quantity"] == 4
