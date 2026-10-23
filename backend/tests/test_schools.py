"""학교 확장 (2026-10-24, 경희대).

- 경희대는 처음에 닫혀 있다 (OPEN_SCHOOLS에 khu.ac.kr을 넣고 seed가 돌아야 열림). 한국외대는 항상 열림
- 닫혀 있을 때: 지금과 똑같다 (경희대 메일 가입 불가, 카드에 학교 없음, 캠퍼스 공개는 본인 선택)
- 열리면: 열린 학교끼리 서로 추천. 어느 학교까지 볼지는 매칭 조건(캠퍼스)이 양쪽으로 정함
  "모든 캠퍼스"면 경희대 자동 포함, 카드에 학교 이름, 캠퍼스 항상 공개
- 같은 과 제외는 "같은 학교 + 같은 과"만 (이름이 같아도 다른 학교 학과는 다른 학과)
- 슈퍼 VIP도 상대가 고른 학교 조건은 지킨다
- 열기 전 테스트: SCHOOL_TEST_EMAILS 계정은 닫힌 학교로 가입되고, 같은 학교 사람·VIP 테스트 계정하고만 서로 보인다
"""

import pytest

from app.core.config import get_settings
from app.models import Department
from app.models.university import Campus, University
from app.scripts import seed
from tests.conftest import (
    UserClient,
    admin_login,
    campus_id,
    department_id,
    discover_ids,
    ready_user,
    set_preferences,
    signup,
)
from tests.test_super_vip import _make_super

KHU = "khu.ac.kr"


def _open_khu(monkeypatch, db):
    monkeypatch.setattr(get_settings(), "open_schools", KHU)
    seed.run()
    db.expire_all()


def _khu(db) -> University:
    return db.query(University).filter(University.email_domain == KHU).one()


def _card(client, profile_id):
    cards = client.get("/api/v1/discover").json()["profiles"]
    return next(c for c in cards if c["profile_id"] == profile_id)


# ---------- 기본 데이터·스위치 ----------

def test_khu_is_seeded_closed_with_two_campuses(db):
    khu = _khu(db)
    assert khu.name == "경희대학교" and khu.active is False
    campuses = {c.name for c in db.query(Campus).filter(Campus.university_id == khu.id)}
    assert campuses == {"서울캠퍼스", "국제캠퍼스"}
    names = {
        n
        for (n,) in db.query(Department.name)
        .join(Campus, Campus.id == Department.campus_id)
        .filter(Campus.university_id == khu.id, Department.active.is_(True))
    }
    assert len(names) == 85
    assert {"의예과·의학과", "컴퓨터공학부 (컴퓨터공학과·인공지능학과)", "국제학과", "작곡과"} <= names
    # 닫혀 있으면 가입 화면 학교 목록에 없다
    unis = UserClient().get("/api/v1/universities").json()["universities"]
    assert [u["email_domain"] for u in unis] == ["hufs.ac.kr"]


def test_open_schools_switch_opens_and_closes_but_hufs_always_open(monkeypatch, db):
    _open_khu(monkeypatch, db)
    assert _khu(db).active is True
    assert {u["email_domain"] for u in UserClient().get("/api/v1/universities").json()["universities"]} == {
        "hufs.ac.kr",
        KHU,
    }
    # 스위치를 빼면 다시 닫힌다. 한국외대는 설정과 상관없이 열려 있다
    monkeypatch.setattr(get_settings(), "open_schools", "")
    seed.run()
    db.expire_all()
    assert _khu(db).active is False
    assert db.query(University).filter(University.email_domain == "hufs.ac.kr").one().active is True


def test_closed_school_email_cannot_sign_up(db):
    r = UserClient().post("/api/v1/auth/email/send-code", json={"email": "someone@khu.ac.kr"})
    assert r.status_code == 400


# ---------- 닫혀 있을 때는 지금과 같다 ----------

def test_single_school_card_has_no_school_and_keeps_hidden_campus(sent_codes, db):
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr", gender="MALE", want="FEMALE")
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr", gender="FEMALE", want="MALE", show_campus=False)
    card = _card(a, b.profile_id)
    assert card["university"] is None
    assert card["campus"] is None  # 본인이 숨긴 캠퍼스는 그대로 숨김
    me = a.get("/api/v1/me").json()
    assert me["multi_school"] is False and me["university_name"] == "한국외국어대학교"


# ---------- 열린 뒤 ----------

def test_open_schools_see_each_other_and_card_shows_school(monkeypatch, sent_codes, db):
    _open_khu(monkeypatch, db)
    admin = admin_login(db)
    hufs = ready_user(sent_codes, db, admin, "h@hufs.ac.kr", gender="MALE", want="FEMALE")
    khu = ready_user(
        sent_codes, db, admin, "k@khu.ac.kr", gender="FEMALE", want="MALE",
        school=KHU, campus="국제캠퍼스", show_campus=False,
    )
    # "모든 캠퍼스"(기본)면 서로 보인다
    assert khu.profile_id in discover_ids(hufs)
    assert hufs.profile_id in discover_ids(khu)
    # 학교 이름이 붙고, 캠퍼스는 본인이 숨겼어도 공개 (2026-10-23 결정)
    card = _card(hufs, khu.profile_id)
    assert card["university"] == "경희대학교" and card["campus"] == "국제캠퍼스"
    assert _card(khu, hufs.profile_id)["university"] == "한국외국어대학교"
    # 서로 LIKE하면 매칭
    assert hufs.post("/api/v1/likes", json={"profile_id": khu.profile_id}).status_code == 200
    r = khu.post("/api/v1/likes", json={"profile_id": hufs.profile_id})
    assert r.status_code == 200 and r.json()["matched"] is True


def test_selected_campuses_limit_schools_both_ways(monkeypatch, sent_codes, db):
    _open_khu(monkeypatch, db)
    admin = admin_login(db)
    only_hufs = [campus_id(db, "서울캠퍼스"), campus_id(db, "글로벌캠퍼스")]
    hufs = ready_user(
        sent_codes, db, admin, "h@hufs.ac.kr", gender="MALE", want="FEMALE",
        prefs={"campus_mode": "SELECTED", "campus_ids": only_hufs},
    )
    khu = ready_user(sent_codes, db, admin, "k@khu.ac.kr", gender="FEMALE", want="MALE", school=KHU)
    assert khu.profile_id not in discover_ids(hufs)
    assert hufs.profile_id not in discover_ids(khu)  # 양쪽 조건: 외대생이 외대만 골랐으면 경희대생에게도 안 보임
    # ID를 직접 넣어도 LIKE 불가
    assert khu.post("/api/v1/likes", json={"profile_id": hufs.profile_id}).status_code == 404

    # 경희대 캠퍼스를 고르면 보인다
    set_preferences(hufs, campus_mode="SELECTED", campus_ids=only_hufs + [campus_id(db, "서울캠퍼스", KHU)])
    assert khu.profile_id in discover_ids(hufs)


def test_same_department_name_at_other_school_is_not_same_department(monkeypatch, sent_codes, db):
    _open_khu(monkeypatch, db)
    admin = admin_login(db)
    # 한국외대 글로벌캠퍼스 "철학과"와 경희대 서울캠퍼스 "철학과"는 다른 학과
    hufs = ready_user(
        sent_codes, db, admin, "h@hufs.ac.kr", gender="MALE", want="FEMALE",
        campus="글로벌캠퍼스", dept="철학과", prefs={"exclude_same_department": True},
    )
    khu = ready_user(
        sent_codes, db, admin, "k@khu.ac.kr", gender="FEMALE", want="MALE", school=KHU, dept="철학과",
        prefs={"exclude_same_department": True},
    )
    assert department_id(db, "철학과") != department_id(db, "철학과", KHU)
    assert khu.profile_id in discover_ids(hufs)


def test_super_vip_keeps_school_condition(monkeypatch, sent_codes, db):
    _open_khu(monkeypatch, db)
    admin = admin_login(db)
    only_hufs = [campus_id(db, "서울캠퍼스"), campus_id(db, "글로벌캠퍼스")]
    hufs_only = ready_user(
        sent_codes, db, admin, "h1@hufs.ac.kr", gender="MALE", want="FEMALE",
        prefs={"campus_mode": "SELECTED", "campus_ids": only_hufs},
    )
    hufs_all = ready_user(sent_codes, db, admin, "h2@hufs.ac.kr", gender="MALE", want="FEMALE")
    sv = ready_user(sent_codes, db, admin, "sv@khu.ac.kr", gender="FEMALE", want="MALE", school=KHU)
    _make_super(admin, db, sv)
    assert sv.profile_id not in discover_ids(hufs_only)  # 외대만 고른 사람에게는 경희대 슈퍼 VIP가 안 뜬다
    assert discover_ids(hufs_all)[0] == sv.profile_id  # 모든 캠퍼스면 맨 앞


def test_preferences_can_choose_open_school_campuses_only(monkeypatch, sent_codes, db):
    admin = admin_login(db)
    hufs = ready_user(sent_codes, db, admin, "h@hufs.ac.kr")
    khu_campus = campus_id(db, "서울캠퍼스", KHU)
    # 닫혀 있으면 경희대 캠퍼스는 고를 수 없고, 목록에도 없다
    r = hufs.put("/api/v1/me/preferences", json={"min_age": 19, "max_age": 30, "campus_mode": "SELECTED", "campus_ids": [khu_campus]})
    assert r.status_code == 400
    listing = hufs.get("/api/v1/me/preferences/campuses").json()
    assert listing["multi_school"] is False
    assert [s["name"] for s in listing["schools"]] == ["한국외국어대학교"]

    _open_khu(monkeypatch, db)
    set_preferences(hufs, campus_mode="SELECTED", campus_ids=[khu_campus])
    listing = hufs.get("/api/v1/me/preferences/campuses").json()
    assert listing["multi_school"] is True
    assert [s["name"] for s in listing["schools"]] == ["한국외국어대학교", "경희대학교"]  # 내 학교가 맨 앞
    assert listing["schools"][0]["mine"] is True
    assert {c["name"] for c in listing["schools"][1]["campuses"]} == {"서울캠퍼스", "국제캠퍼스"}


def test_multi_school_profile_does_not_ask_campus_visibility(monkeypatch, sent_codes, db):
    """학교가 둘 이상 열리면 화면이 캠퍼스 공개를 묻지 않는다 → 학과만 골라도 프로필 완료 (캠퍼스는 공개)."""
    _open_khu(monkeypatch, db)
    from tests.conftest import signup

    client = signup(sent_codes, db, "new@khu.ac.kr", school=KHU, campus="국제캠퍼스")
    r = client.patch(
        "/api/v1/me/profile", json={"department_id": department_id(db, "국제학과", KHU), "show_department": False}
    )
    assert r.status_code == 200, r.text
    profile = client.get("/api/v1/me/profile").json()
    assert profile["show_campus"] is True and profile["campus_always_public"] is True
    assert client.get("/api/v1/me").json()["onboarding"]["profile_done"] is True


# ---------- 열기 전 테스트 계정 ----------

@pytest.fixture
def khu_tester(monkeypatch):
    monkeypatch.setattr(get_settings(), "school_test_emails", f"{KHU}:operator.test@gmail.com")
    return "operator.test@gmail.com"


def test_school_test_account_signs_up_to_closed_school(khu_tester, sent_codes, db):
    admin = admin_login(db)
    tester = ready_user(sent_codes, db, admin, khu_tester, gender="FEMALE", want="ANY", school=KHU)
    assert tester.get("/api/v1/me").json()["university_name"] == "경희대학교"
    # 다른 gmail은 여전히 안 된다
    assert UserClient().post("/api/v1/auth/email/send-code", json={"email": "other@gmail.com"}).status_code == 400


def test_closed_school_tester_only_meets_vip_test_account(khu_tester, sent_codes, db):
    admin = admin_login(db)
    student = ready_user(sent_codes, db, admin, "student@hufs.ac.kr", gender="MALE", want="ANY")
    operator = ready_user(sent_codes, db, admin, "wldns051205@hufs.ac.kr", gender="MALE", want="ANY")  # VIP 테스트 계정
    tester = ready_user(sent_codes, db, admin, khu_tester, gender="FEMALE", want="ANY", school=KHU)

    # 일반 학생과는 서로 안 보이고, ID로 LIKE해도 안 된다
    assert tester.profile_id not in discover_ids(student)
    assert student.profile_id not in discover_ids(tester)
    assert student.post("/api/v1/likes", json={"profile_id": tester.profile_id}).status_code == 404
    assert tester.post("/api/v1/likes", json={"profile_id": student.profile_id}).status_code == 404

    # 운영자 VIP 테스트 계정과는 서로 보이고 매칭·대화까지 된다
    assert tester.profile_id in discover_ids(operator)
    assert operator.profile_id in discover_ids(tester)
    assert _card(operator, tester.profile_id)["university"] == "경희대학교"
    assert operator.post("/api/v1/likes", json={"profile_id": tester.profile_id}).status_code == 200
    r = tester.post("/api/v1/likes", json={"profile_id": operator.profile_id})
    assert r.status_code == 200 and r.json()["matched"] is True


# ---------- 관리자 ----------

def test_admin_sees_school_numbers_and_filter(monkeypatch, sent_codes, db):
    _open_khu(monkeypatch, db)
    admin = admin_login(db)
    ready_user(sent_codes, db, admin, "h@hufs.ac.kr", gender="MALE")
    k = ready_user(sent_codes, db, admin, "k@khu.ac.kr", gender="FEMALE", school=KHU)
    k.get("/api/v1/discover")  # 오늘 접속 기록

    schools = {s["email_domain"]: s for s in admin.get("/api/v1/admin/dashboard").json()["schools"]}
    assert schools[KHU]["open"] is True
    assert schools[KHU]["users_total"] == 1 and schools["hufs.ac.kr"]["users_total"] == 1
    assert schools[KHU]["users_active_female"] == 1

    users = admin.get("/api/v1/admin/users", params={"school": KHU}).json()["users"]
    assert [u["university"] for u in users] == ["경희대학교"]
    detail = admin.get(f"/api/v1/admin/users/{users[0]['user_id']}").json()
    assert detail["university"] == "경희대학교"


def test_verify_tells_school_and_school_list_order(monkeypatch, sent_codes, db):
    _open_khu(monkeypatch, db)
    unis = UserClient().get("/api/v1/universities").json()["universities"]
    assert [u["email_domain"] for u in unis] == ["hufs.ac.kr", KHU]  # 한국외대 버튼이 먼저
    client = UserClient()
    assert client.post("/api/v1/auth/email/send-code", json={"email": "v@khu.ac.kr"}).status_code == 202
    r = client.post("/api/v1/auth/email/verify", json={"email": "v@khu.ac.kr", "code": sent_codes["v@khu.ac.kr"]})
    assert r.status_code == 200
    assert r.json()["university_name"] == "경희대학교" and r.json()["university_id"] == str(_khu(db).id)


# ---------- 경희대 공지 (2026-10-24) ----------

def test_school_notice_before_and_after_open(monkeypatch, sent_codes, db):
    from app.services import announcement_service

    a = signup(sent_codes, db, "a@hufs.ac.kr")
    # 오픈 전: 사전 공지
    assert a.get("/api/v1/me").json()["announcement"] == "khu-notice-2026-10"
    assert a.post("/api/v1/me/announcement/seen", json={"key": "khu-notice-2026-10"}).status_code == 200
    assert a.get("/api/v1/me").json()["announcement"] is None
    # 오픈 공지는 아직 "봤음"으로 보낼 수 없다
    assert a.post("/api/v1/me/announcement/seen", json={"key": "khu-open-2026-10"}).status_code == 404

    # 스위치를 켜면 배포 없이 오픈 공지가 한 번 더 뜬다
    _open_khu(monkeypatch, db)
    assert a.get("/api/v1/me").json()["announcement"] == "khu-open-2026-10"
    assert a.post("/api/v1/me/announcement/seen", json={"key": "khu-open-2026-10"}).status_code == 200
    assert a.get("/api/v1/me").json()["announcement"] is None
    # 오픈 공지를 끄면 아무것도 안 뜬다 (사전 공지가 다시 뜨지 않음)
    monkeypatch.setattr(announcement_service, "SCHOOL_OPEN_NOTICE", None)
    b = signup(sent_codes, db, "b@hufs.ac.kr")
    assert b.get("/api/v1/me").json()["announcement"] == "khu-notice-2026-10"


def test_selected_all_own_campuses_stays_own_school_after_open(monkeypatch, sent_codes, db):
    """오픈 전에 '경희대가 열려도 외대생만'을 고른 사람 (= 외대 캠퍼스 전부를 SELECTED로 저장)."""
    admin = admin_login(db)
    only_hufs = [campus_id(db, "서울캠퍼스"), campus_id(db, "글로벌캠퍼스")]
    hufs = ready_user(
        sent_codes, db, admin, "h@hufs.ac.kr", gender="MALE", want="FEMALE",
        prefs={"campus_mode": "SELECTED", "campus_ids": only_hufs},
    )
    other = ready_user(sent_codes, db, admin, "o@hufs.ac.kr", gender="FEMALE", want="MALE")
    assert other.profile_id in discover_ids(hufs)  # 오픈 전에는 "모든 캠퍼스"와 똑같이 외대생 모두 추천
    _open_khu(monkeypatch, db)
    khu = ready_user(sent_codes, db, admin, "k@khu.ac.kr", gender="FEMALE", want="MALE", school=KHU)
    ids = discover_ids(hufs)
    assert other.profile_id in ids and khu.profile_id not in ids
