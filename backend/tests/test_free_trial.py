"""무료 체험 플랜 (2026-10-06, `무료 체험 플랜 설계`).

- 이용권이 없는 사람(베타 회원 포함)은 LIKE를 평생 3개만. 다 쓰면 다시 안 생긴다 (자정이 지나도)
- 다 써도 추천 보기·PASS·대화는 된다. LIKE는 상대가 나를 LIKE했든 안 했든 똑같이 막힌다
- 체험 LIKE는 하루 한도에서 빼고 센다 → 체험 LIKE를 쓴 날 사도 바로 5개
- 이용권을 사면 체험 끝. 이용권이 끝나도 체험은 다시 안 생긴다
- 탈퇴·재가입해도 체험 사용 개수가 이어진다
- LIKE를 못 하는 사람은 남의 추천에서 같은 등급 안에서 뒤로 (단, 나를 LIKE한 사람은 그대로)
- 이용권·VIP를 살 때마다 사진 바로 재검토 1회 (쌓이지 않음, 7일이 지났으면 깎지 않음)
- 기본 이용권 정가 4,000원, 할인 종료 전 3,000원
"""

import random
import uuid
from datetime import timedelta

import pytest

from app.core.time import utcnow
from app.models.matching import Like
from app.models.photo import AppearanceEvaluation
from app.services import matching_service, membership_service
from tests.conftest import admin_login, approve, discover_ids, jpeg_with_exif, ready_user, signup
from tests.test_membership import paid_world, pay, switch_on, user_of  # noqa: F401  (fixture)


@pytest.fixture
def world(paid_world, monkeypatch):
    switch_on(monkeypatch, paid_world, vip=True)
    return paid_world


def like(client, other):
    return client.post("/api/v1/likes", json={"profile_id": other.profile_id})


def women(sent_codes, db, admin, n, **kw):
    return [
        ready_user(sent_codes, db, admin, f"w{i}@hufs.ac.kr", gender="FEMALE", want="MALE", **kw) for i in range(n)
    ]


# ---------- 체험 LIKE 3개 ----------


def test_trial_three_likes_then_only_like_is_blocked(sent_codes, db, world):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    w = women(sent_codes, db, admin, 5)
    # w4는 나를 LIKE했다 (내가 LIKE하면 바로 매칭될 사람) — 그래도 체험이 끝나면 똑같이 막혀야 한다
    pay(admin, w[4])
    assert like(w[4], me).status_code == 200

    for i in range(3):
        r = like(me, w[i])
        assert r.status_code == 200, r.text
        assert r.json()["likes_left_today"] == 2 - i
    assert user_of(db, me).trial_likes_used == 3
    assert db.query(Like).filter(Like.is_trial.is_(True)).count() == 3

    blocked = like(me, w[3])
    to_liker = like(me, w[4])
    assert blocked.status_code == to_liker.status_code == 409
    assert blocked.json() == to_liker.json() == {"detail": "TRIAL_ENDED"}  # 누가 나를 좋아하는지 티가 안 남

    # 추천·PASS는 된다
    r = me.get("/api/v1/discover")
    assert r.status_code == 200 and r.json()["like_access"] == "none" and r.json()["likes_left_today"] == 0
    assert me.post("/api/v1/passes", json={"profile_id": w[3].profile_id}).status_code == 200
    m = me.get("/api/v1/me").json()["membership"]
    assert m["like_access"] == "none" and m["trial"] == {"limit": 3, "used": 3, "left": 0}


def test_trial_like_can_still_match_and_chat(sent_codes, db, world):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    her = ready_user(sent_codes, db, admin, "her@hufs.ac.kr", gender="FEMALE", want="MALE")
    assert like(me, her).json()["matched"] is False
    r = like(her, me)  # her도 체험 LIKE
    assert r.json()["matched"] is True
    assert her.post(f"/api/v1/matches/{r.json()['match_id']}/messages", json={"body": "안녕"}).status_code == 201


def test_trial_likes_do_not_count_toward_daily_limit_after_buying(sent_codes, db, world):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    w = women(sent_codes, db, admin, 8)
    for i in range(3):
        assert like(me, w[i]).status_code == 200
    pay(admin, me)
    r = me.get("/api/v1/discover").json()
    assert r["like_access"] == "paid" and r["likes_left_today"] == 5
    for i in range(3, 8):
        assert like(me, w[i]).status_code == 200
    assert like(me, ready_user(sent_codes, db, admin, "x@hufs.ac.kr", gender="FEMALE", want="MALE")).status_code == 429


def test_buying_during_trial_ends_trial_and_expiry_does_not_restore_it(sent_codes, db, world):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    her = ready_user(sent_codes, db, admin, "her@hufs.ac.kr", gender="FEMALE", want="MALE")
    assert like(me, her).status_code == 200  # 체험 1개 사용, 2개 남음
    pay(admin, me)
    user = user_of(db, me)
    assert membership_service.trial_left(user) == 0
    user.member_until = utcnow() - timedelta(seconds=1)
    db.commit()
    other = ready_user(sent_codes, db, admin, "o@hufs.ac.kr", gender="FEMALE", want="MALE")
    r = like(me, other)
    assert r.status_code == 409 and r.json()["detail"] == "MEMBERSHIP_REQUIRED"  # 산 적이 있으면 결제 안내 문구
    assert me.get("/api/v1/discover").status_code == 200


def test_trial_user_cannot_request_photo_rereview(sent_codes, db, world):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    r = me.post("/api/v1/me/photos", files={"file": ("me.jpg", jpeg_with_exif(), "image/jpeg")})
    assert r.status_code == 409 and r.json()["detail"] == "MEMBERSHIP_REQUIRED"
    assert me.get("/api/v1/me/photos").json()["rereview_needs_membership"] is True


def test_trial_off_means_no_likes_without_membership(sent_codes, db, world, monkeypatch):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    her = ready_user(sent_codes, db, admin, "her@hufs.ac.kr", gender="FEMALE", want="MALE")
    monkeypatch.setattr(world, "free_trial_likes", 0)
    assert like(me, her).json()["detail"] == "TRIAL_ENDED"


def test_switch_off_is_beta(sent_codes, db, paid_world):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    w = women(sent_codes, db, admin, 4)
    for i in range(4):  # 베타에서는 체험 제한 없이 하루 5개
        assert like(me, w[i]).status_code == 200
    assert user_of(db, me).trial_likes_used == 0


# ---------- 재가입 ----------


def test_trial_count_survives_rejoin(sent_codes, db, world):
    from tests.conftest import choose_department, set_preferences

    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    w = women(sent_codes, db, admin, 4)
    for i in range(3):
        assert like(me, w[i]).status_code == 200
    assert me.delete("/api/v1/me", json={"password": "goodpass123"}).status_code == 200
    again = signup(sent_codes, db, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    choose_department(again, db, "경영학부")
    set_preferences(again)
    m = again.get("/api/v1/me").json()["membership"]
    assert m["trial"]["left"] == 0 and m["like_access"] == "none"


# ---------- 추천 순서 ----------


def test_people_who_cannot_like_go_back_within_same_tier():
    viewer_prefs = matching_service.Preferences("FEMALE", None, None, "ALL")
    cand_prefs = matching_service.Preferences("MALE", None, None, "ALL")
    campus, dept = uuid.uuid4(), uuid.uuid4()

    def person(gender, tier, prefs):
        return matching_service.Person(uuid.uuid4(), gender, 22, campus, dept, prefs, tier=tier)

    viewer = person("MALE", "MID", viewer_prefs)
    same_tier_free = person("FEMALE", "MID", cand_prefs)
    same_tier_paid = person("FEMALE", "MID", cand_prefs)
    other_tier_paid = person("FEMALE", "HIGH", cand_prefs)
    weights = matching_service.Weights(0, 0, 0, 0)
    for seed in range(20):
        ordered = matching_service.order(
            viewer,
            [same_tier_free, other_tier_paid, same_tier_paid],
            weights,
            random.Random(seed),
            cannot_like={same_tier_free.user_id},
        )
        # 같은 등급 안에서는 LIKE 가능한 사람이 먼저, 등급 순서는 그대로
        assert [p.user_id for p in ordered] == [same_tier_paid.user_id, same_tier_free.user_id, other_tier_paid.user_id]


def test_cannot_like_ids(sent_codes, db, world):
    admin = admin_login(db)
    w = women(sent_codes, db, admin, 3)
    used_up, paid = user_of(db, w[0]), user_of(db, w[1])
    used_up.trial_likes_used = 3
    db.commit()
    pay(admin, w[1])
    ids = [user_of(db, c).id for c in w]
    assert membership_service.cannot_like_ids(db, ids) == {used_up.id}
    assert paid.id not in membership_service.cannot_like_ids(db, ids)


def test_discover_still_shows_people_who_cannot_like(sent_codes, db, world):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    w = women(sent_codes, db, admin, 2)
    user = user_of(db, w[0])
    user.trial_likes_used = 3
    db.commit()
    assert set(discover_ids(me)) == {w[0].profile_id, w[1].profile_id}


# ---------- 구매 시 사진 바로 재검토 1회 ----------


def _upload(client):
    return client.post("/api/v1/me/photos", files={"file": ("me.jpg", jpeg_with_exif(), "image/jpeg")})


def test_purchase_rereview_once_per_purchase(sent_codes, db, world):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    pay(admin, me)
    status = me.get("/api/v1/me/photos").json()["resubmit"]
    assert status["purchase_rereview_left"] is True and status["uses_purchase_rereview"] is True

    r = _upload(me)
    assert r.status_code == 201 and r.json()["used_purchase_rereview"] is True
    approve(admin, r.json()["photo_id"])
    status = me.get("/api/v1/me/photos").json()["resubmit"]
    # 구매 혜택을 다 썼으니 이제 평생 1번 "바로 재검토"가 남는다
    assert status["purchase_rereview_left"] is False and status["uses_free_rereview"] is True

    # 한 번 더 사면 다시 1회 (쌓이지 않음 — 두 번 사도 1회)
    pay(admin, me)
    pay(admin, me)
    status = me.get("/api/v1/me/photos").json()["resubmit"]
    assert status["purchase_rereview_left"] is True and status["uses_purchase_rereview"] is True
    r = _upload(me)
    approve(admin, r.json()["photo_id"])
    assert me.get("/api/v1/me/photos").json()["resubmit"]["purchase_rereview_left"] is False


def test_rejected_purchase_rereview_is_not_used(sent_codes, db, world):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    pay(admin, me, "vip")  # VIP도 같은 혜택
    r = _upload(me)
    assert r.json()["used_purchase_rereview"] is True
    rej = admin.put(
        f"/api/v1/admin/photo-reviews/{r.json()['photo_id']}/evaluation",
        json={"decision": "REJECTED", "reject_reason": "얼굴이 잘 보이지 않아요"},
    )
    assert rej.status_code == 200, rej.text
    assert me.get("/api/v1/me/photos").json()["resubmit"]["purchase_rereview_left"] is True


def test_waiting_period_over_does_not_use_purchase_rereview(sent_codes, db, world):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    pay(admin, me)
    uid = user_of(db, me).id
    for ev in db.query(AppearanceEvaluation).filter(AppearanceEvaluation.user_id == uid):
        ev.created_at = utcnow() - timedelta(days=8)
    db.commit()
    r = _upload(me)
    assert r.json()["used_purchase_rereview"] is False and r.json()["used_free_rereview"] is False


# ---------- 가격 ----------


def test_price_regular_and_discount(sent_codes, db, world, monkeypatch):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    assert me.get("/api/v1/me/payment").json()["amount"] == 3000
    m = me.get("/api/v1/me").json()["membership"]
    assert m["price"] == 3000 and m["regular_price"] == 4000 and m["discount_until"] is not None
    monkeypatch.setattr(world, "membership_discount_until", utcnow() - timedelta(seconds=1))
    assert me.get("/api/v1/me/payment").json()["amount"] == 4000  # 아직 "입금했어요" 전이면 지금 가격으로
    monkeypatch.setattr(world, "membership_discount_until", None)
    assert membership_service.price() == 4000
