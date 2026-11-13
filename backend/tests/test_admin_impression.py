"""관리자 현황 · 사용자 관리 보강 (2026-11-13).

- 현황 "오늘 접속"의 남녀 숫자, 오늘 접속한 사람 목록(?visited=today)
- 사용자 관리 목록에 전체적인 인상 점수 (가장 최근 평가)
- 전체적인 인상 점수별 접속자 그래프: 남녀 따로, 7일 이내 접속(활성 사용자 기준)·오늘 접속
"""

from datetime import timedelta

from app.core.time import kst_today, utcnow
from app.models.photo import AppearanceEvaluation
from app.models.user import User, UserDailyVisit
from tests.conftest import admin_login, ready_user, signup


def _user(db, email):
    db.expire_all()
    return db.query(User).filter(User.email == email).one()


def _impression(db, email, score):
    u = _user(db, email)
    ev = db.query(AppearanceEvaluation).filter(AppearanceEvaluation.user_id == u.id).one()
    ev.overall_impression = score
    db.commit()


def _last_visit_days_ago(db, email, days):
    u = _user(db, email)
    db.query(UserDailyVisit).filter(UserDailyVisit.user_id == u.id).delete()
    db.add(UserDailyVisit(user_id=u.id, visit_date=kst_today() - timedelta(days=days)))
    u.last_active_at = utcnow() - timedelta(days=days)
    db.commit()


def _world(sent_codes, db):
    admin = admin_login(db)
    ready_user(sent_codes, db, admin, "m8@hufs.ac.kr", gender="MALE")  # 남 8점, 오늘
    ready_user(sent_codes, db, admin, "m8b@hufs.ac.kr", gender="MALE")  # 남 8점, 3일 전
    ready_user(sent_codes, db, admin, "f6@hufs.ac.kr", gender="FEMALE")  # 여 6점, 오늘
    ready_user(sent_codes, db, admin, "fold@hufs.ac.kr", gender="FEMALE")  # 여 9점, 10일 전 → 그래프에서 빠짐
    signup(sent_codes, db, "nophoto@hufs.ac.kr", gender="FEMALE")  # 사진 검수 전, 오늘 접속
    _impression(db, "m8@hufs.ac.kr", 8)
    _impression(db, "m8b@hufs.ac.kr", 8)
    _impression(db, "f6@hufs.ac.kr", 6)
    _impression(db, "fold@hufs.ac.kr", 9)
    _last_visit_days_ago(db, "m8b@hufs.ac.kr", 3)
    _last_visit_days_ago(db, "fold@hufs.ac.kr", 10)
    return admin


def test_today_gender_counts(sent_codes, db):
    admin = _world(sent_codes, db)
    stats = admin.get("/api/v1/admin/dashboard").json()
    # 오늘 접속: m8, f6, nophoto (사진 검수 여부와 상관없이 센다, "오늘 접속" 숫자와 같은 기준)
    assert stats["users_active_today"] == 3
    assert stats["users_active_today_male"] == 1
    assert stats["users_active_today_female"] == 2


def test_impression_distribution(sent_codes, db):
    admin = _world(sent_codes, db)
    dist = admin.get("/api/v1/admin/dashboard").json()["impression_distribution"]
    assert [b["score"] for b in dist["MALE"]] == list(range(1, 11))
    male = {b["score"]: (b["week"], b["today"]) for b in dist["MALE"]}
    female = {b["score"]: (b["week"], b["today"]) for b in dist["FEMALE"]}
    assert male[8] == (2, 1)
    assert female[6] == (1, 1)
    assert female[9] == (0, 0)  # 10일 전 접속은 7일 이내가 아님
    assert sum(w for w, _ in male.values()) == 2 and sum(w for w, _ in female.values()) == 1  # 사진 검수 전은 빠짐


def test_distribution_uses_latest_evaluation(sent_codes, db):
    admin = _world(sent_codes, db)
    u = _user(db, "f6@hufs.ac.kr")
    old = db.query(AppearanceEvaluation).filter(AppearanceEvaluation.user_id == u.id).one()
    db.add(
        AppearanceEvaluation(
            user_id=u.id, photo_id=old.photo_id, overall_impression=4, style=7, grooming=7, photo_vibe=7,
            evaluator_admin_id=old.evaluator_admin_id, tier="MID", created_at=old.created_at + timedelta(minutes=5),
        )
    )
    db.commit()
    female = {b["score"]: b["week"] for b in admin.get("/api/v1/admin/dashboard").json()["impression_distribution"]["FEMALE"]}
    assert female[4] == 1 and female[6] == 0
    row = next(r for r in admin.get("/api/v1/admin/users").json()["users"] if r["user_id"] == str(u.id))
    assert row["overall_impression"] == 4


def test_user_list_impression_and_today_filter(sent_codes, db):
    admin = _world(sent_codes, db)
    rows = admin.get("/api/v1/admin/users").json()["users"]
    by_nick_score = {r["user_id"]: r["overall_impression"] for r in rows}
    assert by_nick_score[str(_user(db, "m8@hufs.ac.kr").id)] == 8
    assert by_nick_score[str(_user(db, "nophoto@hufs.ac.kr").id)] is None  # 평가 전

    today = admin.get("/api/v1/admin/users", params={"visited": "today"}).json()
    ids = {r["user_id"] for r in today["users"]}
    want = {str(_user(db, e).id) for e in ("m8@hufs.ac.kr", "f6@hufs.ac.kr", "nophoto@hufs.ac.kr")}
    assert ids == want and today["total"] == 3
    assert admin.get("/api/v1/admin/users", params={"visited": "yesterday"}).status_code == 422


def test_dashboard_has_no_personal_info_in_distribution(sent_codes, db):
    admin = _world(sent_codes, db)
    dist = admin.get("/api/v1/admin/dashboard").json()["impression_distribution"]
    for buckets in dist.values():
        for b in buckets:
            assert set(b) == {"score", "week", "today"}  # 숫자만, 누구인지는 없음
