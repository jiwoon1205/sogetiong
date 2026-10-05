"""하루 매칭 3번 → 자동 매칭 정지 (2026-10-06).

- 3번째 매칭까지는 보통대로 보이고, 그 직후 자동 정지 → 4번째부터 숨김
- 자동으로 풀리지 않는다 (다음 날에도 정지). 관리자가 풀면 그때부터 다시 센다
- 정지 사실은 본인에게 안 보이고, 관리자 화면에는 "자동"으로 표시된다
"""

import uuid
from datetime import timedelta

from app.models import Match, PublicProfile, User
from app.models.admin import AuditLog
from app.services import match_limit_service
from tests.conftest import admin_login, ready_user


def user_of(db, client) -> User:
    pid = uuid.UUID(client.profile_id)
    uid = db.query(PublicProfile).filter(PublicProfile.id == pid).one().user_id
    db.expire_all()
    return db.get(User, uid)


def mutual(a, b) -> dict:
    a.post("/api/v1/likes", json={"profile_id": b.profile_id})
    return b.post("/api/v1/likes", json={"profile_id": a.profile_id}).json()


def setup(sent_codes, db, n_men=4):
    admin = admin_login(db)
    w = ready_user(sent_codes, db, admin, "w@hufs.ac.kr", gender="FEMALE")
    men = [ready_user(sent_codes, db, admin, f"m{i}@hufs.ac.kr", gender="MALE") for i in range(n_men)]
    return admin, w, men


def test_third_match_visible_then_suspended(sent_codes, db):
    admin, w, men = setup(sent_codes, db)
    for m in men[:2]:
        assert mutual(w, m)["matched"] is True
        assert user_of(db, w).match_suspended is False

    # 3번째 매칭은 보이고, 그 직후 자동 정지
    assert mutual(w, men[2])["matched"] is True
    assert user_of(db, w).match_suspended is True
    # 상대 남자들은 각각 매칭 1번뿐이라 정지 안 됨
    assert all(user_of(db, m).match_suspended is False for m in men[:3])

    # 4번째는 숨김 (보통 "매칭 안 됨"과 똑같은 응답)
    r = mutual(w, men[3])
    assert r["matched"] is False and r["match_id"] is None
    assert db.query(Match).filter(Match.status == "HIDDEN").count() == 1
    assert len(w.get("/api/v1/matches").json()["matches"]) == 3

    # 본인에게는 흔적이 없다
    assert "match_suspended" not in w.get("/api/v1/me").text

    # 자동 정지 기록 (관리자 없음)
    log = db.query(AuditLog).filter(AuditLog.action == "MATCH_AUTO_SUSPEND").one()
    assert log.admin_id is None and log.metadata_json["matches_today"] == 3

    # 관리자 화면에서는 "자동"으로 보인다
    info = admin.get("/api/v1/admin/match-suspensions").json()
    row = info["users"][0]
    assert row["auto_suspended"] is True and row["suspend_reason"] == "하루 매칭 3번 달성"
    assert row["hidden_matches"] == 1


def test_yesterday_matches_do_not_count(sent_codes, db):
    _, w, men = setup(sent_codes, db)
    for m in men[:2]:
        mutual(w, m)
    # 앞의 두 매칭을 어제 생긴 것으로 바꾼다
    for match in db.query(Match).all():
        match.created_at = match.created_at - timedelta(days=1)
    db.commit()
    mutual(w, men[2])
    assert user_of(db, w).match_suspended is False


def test_stays_suspended_until_admin_unsuspends_then_counts_again(sent_codes, db):
    admin, w, men = setup(sent_codes, db, n_men=5)
    for m in men[:3]:
        mutual(w, m)
    wu = user_of(db, w)
    assert wu.match_suspended is True

    # 다음 날이 되어도 자동으로 풀리지 않는다
    for match in db.query(Match).all():
        match.created_at = match.created_at - timedelta(days=1)
    db.commit()
    assert user_of(db, w).match_suspended is True

    # 관리자가 오늘 풀면, 푼 뒤 매칭만 센다 → 바로 다시 걸리지 않음
    for match in db.query(Match).all():
        match.created_at = match.created_at + timedelta(days=1)  # 다시 오늘로
    db.commit()
    r = admin.patch(f"/api/v1/admin/users/{wu.id}/match-suspension", json={"suspended": False, "reason": "확인"})
    assert r.status_code == 200
    assert mutual(w, men[3])["matched"] is True
    assert user_of(db, w).match_suspended is False

    # 관리자가 직접 건 정지는 "자동"이 아니다
    admin.patch(f"/api/v1/admin/users/{wu.id}/match-suspension", json={"suspended": True, "reason": "수동"})
    row = admin.get("/api/v1/admin/match-suspensions").json()["users"][0]
    assert row["auto_suspended"] is False and row["suspend_reason"] == "수동"


def test_revealed_matches_do_not_count(sent_codes, db):
    admin, w, men = setup(sent_codes, db, n_men=4)
    wu = user_of(db, w)
    admin.patch(f"/api/v1/admin/users/{wu.id}/match-suspension", json={"suspended": True, "reason": "수동"})
    mutual(w, men[0])
    mutual(w, men[1])
    admin.patch(f"/api/v1/admin/users/{wu.id}/match-suspension", json={"suspended": False, "reason": "해제"})
    for m in db.query(Match).filter(Match.status == "HIDDEN").all():
        assert admin.post(f"/api/v1/admin/matches/{m.id}/reveal").status_code == 200
    # 공개한 2개는 세지 않으므로 새 매칭 1개로는 정지되지 않는다
    assert mutual(w, men[2])["matched"] is True
    assert user_of(db, w).match_suspended is False
    assert match_limit_service.matches_today(db, wu.id) == 1


def test_limit_zero_turns_off(sent_codes, db, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "match_auto_suspend_daily", 0)
    _, w, men = setup(sent_codes, db)
    for m in men:
        assert mutual(w, m)["matched"] is True
    assert user_of(db, w).match_suspended is False


def test_vip_tester_is_exempt(sent_codes, db, monkeypatch):
    from app.core.config import get_settings

    s = get_settings()
    monkeypatch.setattr(type(s), "vip_test_email_set", property(lambda self: {"w@hufs.ac.kr"}))
    _, w, men = setup(sent_codes, db)
    for m in men:
        assert mutual(w, m)["matched"] is True
    assert user_of(db, w).match_suspended is False
