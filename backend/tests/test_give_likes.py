"""관리자가 좋아요 더 주기 (2026-10-10).

- 이용권·VIP·베타: 오늘(한국 시간)만 하루 한도에 더한다. 자정이 지나면 사라진다.
- 체험 중·체험 다 씀·이용권 끝: 체험 좋아요를 더 준다.
"""

from datetime import timedelta

import pytest

from app.models.admin import AuditLog
from tests.conftest import admin_login, ready_user
from tests.test_free_trial import like, women, world  # noqa: F401  (fixture)
from tests.test_membership import paid_world, pay, user_of  # noqa: F401  (fixture)


def _give(admin, client_user_id, count, reason="이벤트 보상"):
    return admin.post(f"/api/v1/admin/users/{client_user_id}/likes", json={"count": count, "reason": reason})


def test_trial_user_gets_more_trial_likes(sent_codes, db, world):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    w = women(sent_codes, db, admin, 6)
    for i in range(3):
        assert like(me, w[i]).status_code == 200
    assert like(me, w[3]).status_code == 409  # 체험 다 씀
    uid = user_of(db, me).id

    r = _give(admin, uid, 2)
    assert r.status_code == 200, r.text
    assert r.json()["kind"] == "trial" and r.json()["likes"]["left"] == 2
    d = me.get("/api/v1/discover").json()
    assert d["like_access"] == "trial" and d["likes_left_today"] == 2
    assert like(me, w[3]).status_code == 200
    assert like(me, w[4]).status_code == 200
    assert like(me, w[5]).status_code == 409

    log = db.query(AuditLog).filter(AuditLog.action == "LIKES_GIVE").one()
    assert log.metadata_json["count"] == 2 and log.metadata_json["reason"] == "이벤트 보상"


def test_trial_user_with_likes_left_can_go_above_three(sent_codes, db, world):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    uid = user_of(db, me).id
    assert _give(admin, uid, 2).json()["likes"]["left"] == 5
    m = me.get("/api/v1/me").json()["membership"]
    assert m["trial"] == {"limit": 5, "used": 0, "left": 5}
    d = me.get("/api/v1/discover").json()
    assert d["likes_left_today"] == 5 and d["daily_like_limit"] == 5


def test_paid_user_gets_extra_likes_only_today(sent_codes, db, world, monkeypatch):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    w = women(sent_codes, db, admin, 8)
    pay(admin, me)
    for i in range(5):
        assert like(me, w[i]).status_code == 200, i
    assert like(me, w[5]).status_code == 429
    uid = user_of(db, me).id

    r = _give(admin, uid, 1)
    assert r.json()["kind"] == "today" and r.json()["likes"] == {"access": "paid", "sent": 5, "limit": 6, "left": 1, "bonus_today": 1}
    r = _give(admin, uid, 1)  # 같은 날 또 주면 더해진다
    assert r.json()["likes"]["limit"] == 7 and r.json()["likes"]["bonus_today"] == 2
    assert me.get("/api/v1/discover").json()["likes_left_today"] == 2
    assert like(me, w[5]).status_code == 200
    assert like(me, w[6]).status_code == 200
    assert like(me, w[7]).status_code == 429

    # 관리자 화면 현황
    detail = admin.get(f"/api/v1/admin/users/{uid}").json()
    assert detail["likes_today"]["left"] == 0 and detail["likes_today"]["limit"] == 7

    # 다음 날이 되면 추가분은 사라진다
    from app.core import time as time_mod

    tomorrow = time_mod.kst_today() + timedelta(days=1)
    monkeypatch.setattr("app.services.vip_service.kst_today", lambda now=None: tomorrow)
    assert admin.get(f"/api/v1/admin/users/{uid}").json()["likes_today"]["bonus_today"] == 0


@pytest.mark.parametrize("count", [0, 21])
def test_give_likes_validation(sent_codes, db, world, count):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    assert _give(admin, user_of(db, me).id, count).status_code == 422
