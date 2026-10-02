"""캠퍼스·학과 (A-2): 학과 필수·변경 불가, 공개 여부, 같은 과 제외, 매칭 조건 변경 제한, 학과 목록."""

from app.core.config import get_settings
from app.models import AuditLog, Campus, Department, PublicProfile
from app.scripts import seed
from tests.conftest import (
    UserClient,
    admin_login,
    approve,
    campus_id,
    choose_department,
    department_id,
    discover_ids,
    ready_user,
    set_preferences,
    signup,
    upload_photo,
)


# ---------- 학과 목록 ----------

def test_real_department_list_is_seeded(db):
    names = {n for (n,) in db.query(Department.name).filter(Department.active.is_(True))}
    assert {"ELLT학과", "경영학부", "컴퓨터공학부", "자유전공학부(서울)", "영어통번역학부"} <= names
    # 확인이 필요해 뺀 학과, 2016년 이전 모집중지 학과는 없다
    assert not names & {"영어학부", "KFL학부", "경영정보학과"}


def test_seed_deactivates_departments_not_in_list(db):
    campus = db.query(Campus).filter(Campus.name == "서울캠퍼스").one()
    db.add(Department(campus_id=campus.id, name="예전예시학과"))
    db.commit()
    seed.run()
    db.expire_all()
    old = db.query(Department).filter(Department.name == "예전예시학과").one()
    assert old.active is False  # 삭제하지 않고 비활성화 → 이미 고른 사람의 데이터는 그대로
    assert "예전예시학과" not in UserClient().get(f"/api/v1/campuses/{campus.id}/departments").text


def test_support_email_is_public(db):
    assert UserClient().get("/api/v1/support").json() == {"email": get_settings().support_email}


# ---------- 학과 필수 ----------

def test_department_is_required_to_discover_and_like(sent_codes, db):
    admin = admin_login(db)
    other = ready_user(sent_codes, db, admin, "o@hufs.ac.kr")
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    assert a.get("/api/v1/me").json()["onboarding"]["profile_done"] is False
    set_preferences(a)
    approve(admin, upload_photo(a))
    r = a.get("/api/v1/discover")
    assert r.status_code == 409 and r.json()["detail"] == "DEPARTMENT_REQUIRED"
    assert a.post("/api/v1/likes", json={"profile_id": other.profile_id}).status_code == 409
    # 학과 없는 사람은 다른 사람의 추천에도 안 나온다
    assert a.profile_id not in discover_ids(other)

    choose_department(a, db, "국제학부")
    assert a.get("/api/v1/me").json()["onboarding"]["profile_done"] is True
    assert other.profile_id in discover_ids(a)


def test_visibility_must_be_chosen_with_department(sent_codes, db):
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    dept = department_id(db, "국제학부")
    r = a.patch("/api/v1/me/profile", json={"department_id": dept})
    assert r.status_code == 400
    r = a.patch("/api/v1/me/profile", json={"department_id": dept, "show_department": True})
    assert r.status_code == 400  # 캠퍼스 공개 여부도 골라야 함
    r = a.patch("/api/v1/me/profile", json={"department_id": dept, "show_department": False, "show_campus": False})
    assert r.status_code == 200
    body = r.json()
    assert body["department_locked"] is True and body["show_campus"] is False
    # 본인 화면용 이름은 따로 오고, 카드(다른 사람이 보는 모습)에는 숨겨진다
    assert body["department_name"] == "국제학부" and body["department"] is None and body["campus"] is None


def test_department_from_other_campus_is_rejected(sent_codes, db):
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    r = a.patch(
        "/api/v1/me/profile",
        json={"department_id": department_id(db, "컴퓨터공학부"), "show_department": True, "show_campus": True},
    )
    assert r.status_code == 400


# ---------- 학과 변경 불가 → 관리자가 변경 ----------

def test_department_cannot_be_changed_by_user(sent_codes, db):
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    choose_department(a, db, "국제학부")
    r = a.patch("/api/v1/me/profile", json={"department_id": department_id(db, "경영학부"), "show_department": True})
    assert r.status_code == 409
    assert get_settings().support_email in r.json()["detail"]
    # 같은 학과를 다시 보내는 건 괜찮다 (저장 버튼을 여러 번 누르는 경우)
    r = a.patch("/api/v1/me/profile", json={"department_id": department_id(db, "국제학부"), "bio": "안녕하세요"})
    assert r.status_code == 200 and r.json()["department_name"] == "국제학부"
    # 공개 여부는 언제든 바꿀 수 있다
    r = a.patch("/api/v1/me/profile", json={"show_department": False, "show_campus": False})
    assert r.status_code == 200 and r.json()["department"] is None


def test_admin_changes_department_with_audit(sent_codes, db):
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    choose_department(a, db, "국제학부")
    user_id = str(db.query(PublicProfile).one().user_id)

    moderator = admin_login(db, "MODERATOR")
    body = {"department_id": department_id(db, "경영학부"), "reason": "가입 메일로 요청"}
    assert moderator.patch(f"/api/v1/admin/users/{user_id}/department", json=body).status_code == 403

    superadmin = admin_login(db, "SUPER_ADMIN")
    wrong_campus = {"department_id": department_id(db, "컴퓨터공학부"), "reason": "가입 메일로 요청"}
    assert superadmin.patch(f"/api/v1/admin/users/{user_id}/department", json=wrong_campus).status_code == 400
    r = superadmin.patch(f"/api/v1/admin/users/{user_id}/department", json=body)
    assert r.status_code == 200, r.text
    assert a.get("/api/v1/me/profile").json()["department_name"] == "경영학부"
    assert superadmin.get(f"/api/v1/admin/users/{user_id}").json()["department"]["name"] == "경영학부"
    log = db.query(AuditLog).filter(AuditLog.action == "USER_DEPARTMENT_CHANGE").one()
    assert log.metadata_json["reason"] == "가입 메일로 요청"
    assert "학과가 변경" in a.get("/api/v1/notifications").text


# ---------- 캠퍼스 공개 여부 ----------

def test_hidden_campus_is_not_on_card(sent_codes, db):
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr")
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr", dept="국제학부", show_campus=False, show_department=False)
    card = next(c for c in a.get("/api/v1/discover").json()["profiles"] if c["profile_id"] == b.profile_id)
    assert card["campus"] is None and card["department"] is None
    card = next(c for c in b.get("/api/v1/discover").json()["profiles"] if c["profile_id"] == a.profile_id)
    assert card["campus"] == "서울캠퍼스" and card["department"] == "경영학부"
    # 비공개여도 캠퍼스 필터는 그대로 적용된다
    set_preferences(a, campus_mode="SELECTED", campus_ids=[campus_id(db, "글로벌캠퍼스")])
    assert b.profile_id not in discover_ids(a)


# ---------- 매칭 조건 변경 제한 ----------

def test_preferences_can_change_three_times_a_day(sent_codes, db):
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    set_preferences(a)  # 처음 저장은 세지 않음
    assert a.get("/api/v1/me/preferences").json()["changes_left_today"] == 3
    set_preferences(a)  # 같은 내용으로 다시 저장해도 세지 않음
    for age in (25, 26, 27):
        set_preferences(a, max_age=age)
    assert a.get("/api/v1/me/preferences").json()["changes_left_today"] == 0
    r = a.put("/api/v1/me/preferences", json={"preferred_gender": "ANY", "min_age": 19, "max_age": 28, "campus_mode": "ALL"})
    assert r.status_code == 429

    # 한국 시간 자정이 지나면 (24시간이 안 됐어도) 다시 바꿀 수 있다
    from datetime import timedelta

    from app.core.time import kst_day_start
    from app.models import MatchingPreference

    pref = db.query(MatchingPreference).one()
    pref.change_window_started_at = kst_day_start() - timedelta(minutes=1)  # 어젯밤 11시 59분에 바꾼 것으로
    db.commit()
    assert a.get("/api/v1/me/preferences").json()["changes_left_today"] == 3
    set_preferences(a, max_age=28)
    assert a.get("/api/v1/me/preferences").json()["changes_left_today"] == 2


def test_preferences_window_resets_at_kst_midnight_not_after_24_hours():
    """밤 11시에 처음 바꾸면 → 다음 날 0시에 풀린다 (다음 날 밤 11시가 아니라)."""
    from datetime import datetime, timezone

    from app.api.v1.profiles import _window_expired
    from app.models import MatchingPreference

    # 10월 1일 밤 11시(한국) = 10월 1일 14시(UTC)
    pref = MatchingPreference(change_window_started_at=datetime(2026, 10, 1, 14, 0, tzinfo=timezone.utc))
    assert not _window_expired(pref, datetime(2026, 10, 1, 14, 59, tzinfo=timezone.utc))  # 같은 날 11시 59분
    assert _window_expired(pref, datetime(2026, 10, 1, 15, 1, tzinfo=timezone.utc))  # 다음 날 0시 1분
    # SQLite에서 꺼내면 시간대 정보가 없다 → 그래도 UTC로 보고 똑같이 계산
    pref.change_window_started_at = datetime(2026, 10, 1, 14, 0)
    assert _window_expired(pref, datetime(2026, 10, 1, 15, 1, tzinfo=timezone.utc))
    assert not _window_expired(pref, datetime(2026, 10, 1, 14, 59, tzinfo=timezone.utc))
