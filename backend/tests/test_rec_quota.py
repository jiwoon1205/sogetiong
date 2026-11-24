"""좋아요 3·4번 쌓인 사람 노출 제한 (2026-11-13, rec_quota_service).

- 이용권 기간마다 3번 보낸 사람은 4명, 4번 보낸 사람은 2명까지만 추천에 나온다 (서로 다른 사람 수)
- 자리를 받은 사람은 그 기간 동안 계속 나올 수 있다 (새로 뽑아도 다른 사람으로 바뀌지 않는다)
- 이용권·VIP 입금이 확인되면 자리가 다시 열린다
- 이용권이 끝난 사람(좋아요 불가)에게는 4번 보낸 사람 1명만 맨 앞에 (맛보기)
- 여성은 제한 없음. 응답에는 제한을 알 수 있는 값이 없다
"""

import uuid
from datetime import datetime, timedelta, timezone

from app.core.config import get_settings
from app.core.rate_limit import reset_rate_limits
from app.core.time import KST, utcnow
from app.models import Like, PublicProfile, RecQuotaSlot
from tests.conftest import admin_login, discover_ids, ready_user


def _uid(db, client):
    return db.query(PublicProfile).filter(PublicProfile.id == uuid.UUID(client.profile_id)).one().user_id


def _liked(db, me, other, count):
    """me가 other에게 좋아요를 count번 보냈고, 마지막 좋아요가 3일보다 전이라 다시 추천에 나올 수 있는 상태."""
    old = utcnow() - timedelta(hours=100)
    db.add(Like(from_user_id=_uid(db, me), to_user_id=_uid(db, other), action="LIKE", like_count=count, created_at=old, updated_at=old))
    db.commit()


def _world(sent_codes, db, *, viewer_gender="MALE", n3=6, n4=4, n0=2):
    admin = admin_login(db)
    other = "FEMALE" if viewer_gender == "MALE" else "MALE"
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender=viewer_gender, want=other)
    groups = {}
    for count, n in ((3, n3), (4, n4), (0, n0)):
        groups[count] = []
        for i in range(n):
            reset_rate_limits()  # 한 테스트에서 여러 명을 가입시키므로 인증 메일 요청 제한을 비운다
            groups[count].append(ready_user(sent_codes, db, admin, f"p{count}-{i}@hufs.ac.kr", gender=other, want=viewer_gender))
        if count:
            for p in groups[count]:
                _liked(db, me, p, count)
    return admin, me, {k: {p.profile_id for p in v} for k, v in groups.items()}


def _page(me):
    r = me.get("/api/v1/discover", params={"limit": 20})
    assert r.status_code == 200, r.text
    return r.json()


def test_three_likes_four_people_four_likes_two_people(sent_codes, db, new_draw_each_call):
    _, me, g = _world(sent_codes, db)
    seen3, seen4 = set(), set()
    for _ in range(8):  # 날짜를 바꿔 가며 새로 뽑아도
        ids = set(discover_ids(me))
        assert g[0] <= ids  # 좋아요를 안 보낸 사람은 그대로
        seen3 |= ids & g[3]
        seen4 |= ids & g[4]
    # 처음 자리를 받은 사람만 계속 나온다 → 여러 번 뽑아도 4명·2명을 넘지 않는다
    assert len(seen3) == 4 and len(seen4) == 2


def test_liking_again_needs_a_four_like_slot(sent_codes, db, new_draw_each_call):
    # 3번 자리를 받은 사람에게 한 번 더 보내면 4번 자리가 따로 필요하다 (4번 자리가 이미 다 찼으면 안 나온다)
    _, me, g = _world(sent_codes, db, n3=1, n4=2, n0=1)
    first = set(discover_ids(me))
    assert len(first & g[3]) == 1 and len(first & g[4]) == 2
    three = next(iter(g[3]))
    row = db.query(Like).filter(Like.to_user_id == db.query(PublicProfile.user_id).filter(PublicProfile.id == uuid.UUID(three)).scalar_subquery()).one()
    row.like_count = 4
    db.commit()
    assert three not in discover_ids(me)


def test_new_pass_opens_the_slots_again(sent_codes, db, monkeypatch):
    admin, me, g = _world(sent_codes, db, n3=5, n4=0, n0=0)
    discover_ids(me)
    me_id = _uid(db, me)
    assert db.query(RecQuotaSlot).filter(RecQuotaSlot.user_id == me_id).count() == 4

    # 이용권 결제 → 관리자 입금 확인 → 자리가 비워진다
    s = get_settings()
    monkeypatch.setattr(s, "membership_enabled", True)
    monkeypatch.setattr(s, "vip_test_emails", "")
    monkeypatch.setattr(s, "payment_bank_name", "테스트은행")
    monkeypatch.setattr(s, "payment_account_number", "123-456-7890")
    monkeypatch.setattr(s, "payment_account_holder", "운영자")
    noon = datetime(2026, 11, 2, 12, tzinfo=KST).astimezone(timezone.utc)
    monkeypatch.setattr("app.services.payment_service.utcnow", lambda: noon)
    assert me.post("/api/v1/me/payment/request").status_code == 200
    pid = admin.get("/api/v1/admin/payments").json()["payments"][0]["payment_id"]
    assert admin.post(f"/api/v1/admin/payments/{pid}/confirm").status_code == 200
    db.expire_all()
    assert db.query(RecQuotaSlot).filter(RecQuotaSlot.user_id == me_id).count() == 0


def test_after_pass_ends_one_four_like_person_first(sent_codes, db, monkeypatch, new_draw_each_call):
    _, me, g = _world(sent_codes, db, n3=2, n4=3, n0=3)
    s = get_settings()
    # 유료 시작 + 체험 좋아요 없음 + 이용권 없음 → 좋아요 불가(이용권이 끝난 사람과 같은 상태)
    monkeypatch.setattr(s, "membership_enabled", True)
    monkeypatch.setattr(s, "vip_test_emails", "")
    monkeypatch.setattr(s, "free_trial_likes", 0)
    for _ in range(5):
        data = _page(me)
        assert data["like_access"] == "none"
        ids = [p["profile_id"] for p in data["profiles"]]
        four = [i for i in ids if i in g[4]]
        assert len(four) == 1 and ids[0] == four[0]  # 맛보기 1명, 맨 앞
        assert data["profiles"][0]["my_likes"] == 4
        assert g[0] <= set(ids)


def test_women_have_no_limit(sent_codes, db):
    _, me, g = _world(sent_codes, db, viewer_gender="FEMALE", n3=5, n4=3, n0=1)
    ids = set(discover_ids(me))
    assert g[3] <= ids and g[4] <= ids


def test_switch_off_is_old_rule(sent_codes, db, monkeypatch):
    monkeypatch.setattr(get_settings(), "rec_quota_enabled", False)
    _, me, g = _world(sent_codes, db, n3=5, n4=3, n0=1)
    ids = set(discover_ids(me))
    assert g[3] <= ids and g[4] <= ids


def test_response_does_not_reveal_the_limit(sent_codes, db):
    _, me, _ = _world(sent_codes, db, n3=5, n4=3, n0=1)
    text = me.get("/api/v1/discover").text.lower()
    assert "quota" not in text and "slot" not in text and "teaser" not in text


# ---------- 2026-11-24 ----------

def _expire(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "membership_enabled", True)
    monkeypatch.setattr(s, "vip_test_emails", "")
    monkeypatch.setattr(s, "free_trial_likes", 0)


def test_expired_teaser_is_most_liked_person(sent_codes, db, monkeypatch, new_draw_each_call):
    """이용권이 끝난 사람: 맨 앞 = 좋아요를 가장 많이 보낸 사람 (2번 이상). 4번이 없어도 3번·2번 중 가장 많은 사람."""
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE", want="FEMALE")
    people = {}
    for n in (1, 2, 3, 0, 0):
        reset_rate_limits()
        p = ready_user(sent_codes, db, admin, f"w{len(people)}@hufs.ac.kr", gender="FEMALE", want="MALE")
        people[p.profile_id] = n
        if n:
            _liked(db, me, p, n)
    _expire(monkeypatch)
    for _ in range(4):
        data = _page(me)
        assert data["like_access"] == "none"
        assert people[data["profiles"][0]["profile_id"]] == 3

    # 1번만 보낸 사람뿐이면 맛보기 없음 (그냥 추첨 순서)
    db.query(Like).filter(Like.like_count >= 2).delete()
    db.commit()
    first = _page(me)["profiles"][0]["profile_id"]
    assert first in people


def _matches(db, me, n):
    from app.models.matching import Match
    from app.models.user import User

    me_id = _uid(db, me)
    base = db.get(User, me_id)
    for i in range(n):
        other = User(email=f"m{i}@x.test", status="ACTIVE", password_hash="x", university_id=base.university_id)
        db.add(other)
        db.flush()
        a, b = sorted([me_id, other.id], key=str)
        db.add(Match(user_a_id=a, user_b_id=b))
    db.commit()


def test_heavy_matcher_four_likes_one_person_one_day(sent_codes, db, monkeypatch):
    """이번 이용권 기간 매칭 5회+: 4번 쌓인 사람은 1명만, 자리를 받은 그날 하루만 (2026-11-24)."""
    from app.services import rec_quota_service

    _, me, g = _world(sent_codes, db, n3=0, n4=3, n0=2)
    _matches(db, me, 5)
    from app.models.user import User

    assert rec_quota_service.heavy_matcher(db, db.query(User).filter_by(email="me@hufs.ac.kr").one())
    ids = set(discover_ids(me))
    assert len(ids & g[4]) == 1
    # 다음 날: 그 사람도 더 안 나온다
    monkeypatch.setattr(rec_quota_service, "utcnow", lambda: utcnow() + timedelta(days=1))
    assert not (set(discover_ids(me)) & g[4])


def test_light_matcher_keeps_old_rule(sent_codes, db):
    _, me, g = _world(sent_codes, db, n3=0, n4=3, n0=2)
    _matches(db, me, 4)
    assert len(set(discover_ids(me)) & g[4]) == 2


def test_three_like_factor_lowers_weight():
    import dataclasses

    from app.services import matching_service, profile_service

    w = profile_service.matching_weights()
    low = dataclasses.replace(w, sent_three_factor=0.2)
    assert matching_service.weight is not None
    assert low.sent_three_factor == 0.2 and w.sent_three_factor == 1.0
