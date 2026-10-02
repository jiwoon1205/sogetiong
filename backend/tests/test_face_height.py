"""얼굴상·키 (2026-10-02): 둘 다 선택사항, 얼굴상은 목록에서 1개, 키는 140~210cm. 카드에 그대로 보이고 걸러보기에는 안 쓴다."""

from app.schemas.profile import FACE_TYPES
from tests.conftest import admin_login, ready_user, signup


def test_face_type_and_height_are_optional_and_saved(sent_codes, db):
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    me = a.get("/api/v1/me/profile").json()
    assert me["face_type"] is None and me["height_cm"] is None  # 처음에는 비어 있다

    r = a.patch("/api/v1/me/profile", json={"face_type": "고양이상", "height_cm": 172})
    assert r.status_code == 200, r.text
    assert r.json()["face_type"] == "고양이상" and r.json()["height_cm"] == 172

    # 다른 항목만 고치면 얼굴상·키는 그대로
    r = a.patch("/api/v1/me/profile", json={"bio": "안녕하세요"})
    assert r.json()["face_type"] == "고양이상" and r.json()["height_cm"] == 172

    # null을 보내면 지운다
    r = a.patch("/api/v1/me/profile", json={"face_type": None, "height_cm": None})
    assert r.json()["face_type"] is None and r.json()["height_cm"] is None


def test_face_type_must_be_in_list(sent_codes, db):
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    assert len(FACE_TYPES) == 10
    for bad in ("강쥐상", "고양이상, 여우상", "010-1234-5678", ""):
        assert a.patch("/api/v1/me/profile", json={"face_type": bad}).status_code == 422, bad
    for good in FACE_TYPES:
        assert a.patch("/api/v1/me/profile", json={"face_type": good}).status_code == 200, good


def test_height_range(sent_codes, db):
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    for bad in (139, 211, 0, -170, "백칠십", 172.5):
        assert a.patch("/api/v1/me/profile", json={"height_cm": bad}).status_code == 422, bad
    for good in (140, 165, 210):
        assert a.patch("/api/v1/me/profile", json={"height_cm": good}).status_code == 200, good


def test_card_shows_face_type_and_height_but_does_not_filter(sent_codes, db):
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr")
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr", dept="국제학부")
    c = ready_user(sent_codes, db, admin, "c@hufs.ac.kr", dept="국제학부")  # 아무것도 안 적은 사람
    b.patch("/api/v1/me/profile", json={"face_type": "공룡상", "height_cm": 181})

    cards = {card["profile_id"]: card for card in a.get("/api/v1/discover").json()["profiles"]}
    assert cards[b.profile_id]["face_type"] == "공룡상"
    assert cards[b.profile_id]["height_cm"] == 181
    # 안 적은 사람도 똑같이 추천에 나온다 (불이익 없음)
    assert cards[c.profile_id]["face_type"] is None and cards[c.profile_id]["height_cm"] is None
