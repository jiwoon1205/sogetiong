"""5개 학교 추가 (2026-11-21): 고려대(서울·세종) · 서울시립대 · 서일대 · 성신여대 · 동덕여대.

- 처음에는 모두 닫혀 있다 (OPEN_SCHOOLS에 메일 뒷부분을 넣어야 열림)
- 여대(성신·동덕) 메일로 가입하면 성별은 보낸 값과 상관없이 여성
- 새 학교가 하나라도 열리면 "학교 추가 + 친구 초대" 공지가 자동으로 뜬다 (신규 가입자에게도)
"""

from app.core.config import get_settings
from app.models import Department
from app.models.profile import PublicProfile
from app.models.university import Campus, University
from app.models.user import User
from app.scripts import seed
from app.services import announcement_service
from tests.conftest import UserClient, signup

NEW = {
    "korea.ac.kr": ("고려대학교", {"서울캠퍼스", "세종캠퍼스"}),
    "uos.ac.kr": ("서울시립대학교", {"서울캠퍼스"}),
    "seoil.ac.kr": ("서일대학교", {"서울캠퍼스"}),
    "sungshin.ac.kr": ("성신여자대학교", {"돈암수정캠퍼스", "미아운정그린캠퍼스"}),
    "dongduk.ac.kr": ("동덕여자대학교", {"서울캠퍼스"}),
}


def _open(monkeypatch, db, domains: str):
    monkeypatch.setattr(get_settings(), "open_schools", domains)
    seed.run()
    db.expire_all()


def test_new_schools_seeded_closed_with_campuses_and_departments(db):
    for domain, (name, campuses) in NEW.items():
        uni = db.query(University).filter(University.email_domain == domain).one()
        assert uni.name == name and uni.active is False
        rows = db.query(Campus).filter(Campus.university_id == uni.id).all()
        assert {c.name for c in rows} == campuses
        for c in rows:
            assert db.query(Department).filter(Department.campus_id == c.id, Department.active.is_(True)).count() >= 10
    # 닫혀 있으면 가입 화면 목록에 없다
    unis = UserClient().get("/api/v1/universities").json()["universities"]
    assert not {u["email_domain"] for u in unis} & set(NEW)


def test_open_all_five_and_women_only_flag(monkeypatch, db):
    _open(monkeypatch, db, "khu.ac.kr," + ",".join(NEW))
    unis = {u["email_domain"]: u for u in UserClient().get("/api/v1/universities").json()["universities"]}
    assert set(NEW) | {"hufs.ac.kr", "khu.ac.kr"} == set(unis)
    assert {d for d, u in unis.items() if u["women_only"]} == {"sungshin.ac.kr", "dongduk.ac.kr"}


def test_womens_university_signup_is_always_female(monkeypatch, sent_codes, db):
    _open(monkeypatch, db, "sungshin.ac.kr,dongduk.ac.kr,korea.ac.kr")
    # 인증번호 확인 응답에 fixed_gender
    c = UserClient()
    c.post("/api/v1/auth/email/send-code", json={"email": "s1@sungshin.ac.kr"})
    r = c.post("/api/v1/auth/email/verify", json={"email": "s1@sungshin.ac.kr", "code": sent_codes["s1@sungshin.ac.kr"]})
    assert r.json()["fixed_gender"] == "FEMALE" and r.json()["university_name"] == "성신여자대학교"

    # 남성으로 보내도 여성으로 저장된다 (추천 상대는 남성)
    signup(sent_codes, db, "s2@sungshin.ac.kr", gender="MALE", campus="돈암수정캠퍼스", school="sungshin.ac.kr")
    signup(sent_codes, db, "d1@dongduk.ac.kr", gender="MALE", school="dongduk.ac.kr")
    for email in ("s2@sungshin.ac.kr", "d1@dongduk.ac.kr"):
        user = db.query(User).filter(User.email == email).one()
        assert db.query(PublicProfile).filter(PublicProfile.user_id == user.id).one().gender == "FEMALE"
        assert user.private_profile.preferred_gender == "MALE"

    # 공학은 고른 대로
    signup(sent_codes, db, "k1@korea.ac.kr", gender="MALE", campus="세종캠퍼스", school="korea.ac.kr")
    user = db.query(User).filter(User.email == "k1@korea.ac.kr").one()
    assert db.query(PublicProfile).filter(PublicProfile.user_id == user.id).one().gender == "MALE"
    c2 = UserClient()
    c2.post("/api/v1/auth/email/send-code", json={"email": "k2@korea.ac.kr"})
    r = c2.post("/api/v1/auth/email/verify", json={"email": "k2@korea.ac.kr", "code": sent_codes["k2@korea.ac.kr"]})
    assert r.json()["fixed_gender"] is None


def test_new_schools_notice_shows_when_any_new_school_opens(monkeypatch, sent_codes, db):
    a = signup(sent_codes, db, "old@hufs.ac.kr")
    before = a.get("/api/v1/me").json()["announcement"]
    assert not (before or "").startswith(announcement_service.NEW_SCHOOLS_NOTICE)  # 닫혀 있으면 안 뜸

    _open(monkeypatch, db, "khu.ac.kr,uos.ac.kr")
    key = announcement_service.current_key(True, new_schools=True)
    assert key.startswith(announcement_service.NEW_SCHOOLS_NOTICE)
    assert a.get("/api/v1/me").json()["announcement"] == key
    assert a.post("/api/v1/me/announcement/seen", json={"key": key}).status_code == 200
    assert a.get("/api/v1/me").json()["announcement"] is None

    # 새로 가입한 사람에게도 뜬다 (친구 초대 안내라서)
    b = signup(sent_codes, db, "new@uos.ac.kr", school="uos.ac.kr")
    assert b.get("/api/v1/me").json()["announcement"] == key


def test_school_removed_from_list_is_closed_even_if_in_open_schools(monkeypatch, db):
    """SCHOOLS에서 뺀 학교(삼육보건대처럼)는 DB에 남아 있어도 닫힌다."""
    db.add(University(name="삼육보건대학교", email_domain="shu.ac.kr", active=True))
    db.commit()
    _open(monkeypatch, db, "shu.ac.kr,korea.ac.kr")
    assert db.query(University).filter(University.email_domain == "shu.ac.kr").one().active is False
    assert db.query(University).filter(University.email_domain == "korea.ac.kr").one().active is True
    unis = {u["email_domain"] for u in UserClient().get("/api/v1/universities").json()["universities"]}
    assert "shu.ac.kr" not in unis


def test_more_schools_seeded_closed_with_all_campuses(db):
    """2026-11-21 추가 13개: 모두 닫힌 채로, 지방 캠퍼스까지."""
    from app.scripts.schools_more import MORE_SCHOOLS

    assert len(MORE_SCHOOLS) == 13
    for school in MORE_SCHOOLS:
        uni = db.query(University).filter(University.email_domain == school["email_domain"]).one()
        assert uni.active is False and uni.name == school["name"]
        assert {c.name for c in db.query(Campus).filter(Campus.university_id == uni.id)} == set(school["campuses"])
    yonsei = db.query(University).filter(University.email_domain == "yonsei.ac.kr").one()
    assert {c.name for c in db.query(Campus).filter(Campus.university_id == yonsei.id)} == {
        "신촌캠퍼스", "국제캠퍼스", "미래캠퍼스"
    }


def test_subdomain_and_alias_email_find_the_school(monkeypatch, sent_codes, db):
    """g.skku.edu → 성균관대, sejong.ac.kr → 세종대 (학교가 메일 주소를 여러 개 쓰는 경우)."""
    _open(monkeypatch, db, "skku.edu,sju.ac.kr")
    signup(sent_codes, db, "a@g.skku.edu", campus="자연과학캠퍼스", school="skku.edu")
    signup(sent_codes, db, "b@sejong.ac.kr", school="sju.ac.kr")
    names = {
        e: db.query(University).get(db.query(User).filter(User.email == e).one().university_id).name
        for e in ("a@g.skku.edu", "b@sejong.ac.kr")
    }
    assert names == {"a@g.skku.edu": "성균관대학교", "b@sejong.ac.kr": "세종대학교"}
    # "ac.kr"만 같은 다른 주소는 안 된다
    r = UserClient().post("/api/v1/auth/email/send-code", json={"email": "x@fake.ac.kr"})
    assert r.status_code == 400


def test_new_schools_notice_repeats_every_two_days_for_two_weeks(sent_codes, db):
    """2일에 한 번씩 모두에게 (본 사람에게도), 2주가 지나면 계정당 한 번으로 (2026-11-21)."""
    from datetime import datetime, timedelta

    from app.core.time import KST

    svc = announcement_service
    a = signup(sent_codes, db, "rep@hufs.ac.kr")
    user = db.query(User).filter(User.email == "rep@hufs.ac.kr").one()
    day = lambda d: datetime.combine(svc.NEW_SCHOOLS_REPEAT_FROM + timedelta(days=d), datetime.min.time(), KST).replace(hour=12)

    k0 = svc.pending(user, day(0), multi_school=True, new_schools=True)
    assert k0 == f"{svc.NEW_SCHOOLS_NOTICE}@{svc.NEW_SCHOOLS_REPEAT_FROM.isoformat()}"
    user.announcement_seen = k0
    assert svc.pending(user, day(1), multi_school=True, new_schools=True) is None  # 같은 2일 안에는 다시 안 뜸
    k2 = svc.pending(user, day(2), multi_school=True, new_schools=True)
    assert k2 is not None and k2 != k0  # 2일 뒤 다시 뜸
    user.announcement_seen = k2
    last = (svc.NEW_SCHOOLS_REPEAT_UNTIL - svc.NEW_SCHOOLS_REPEAT_FROM).days
    assert svc.pending(user, day(last), multi_school=True, new_schools=True) is not None  # 마지막 날까지
    # 기간이 끝나면: 한 번이라도 본 사람에게는 안 뜸
    assert svc.pending(user, day(last + 1), multi_school=True, new_schools=True) is None
    assert a is not None
