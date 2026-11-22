"""사용자 설문 (2026-11-22: '대학교 친구' 없애기 찬반 투표로 교체).

- 처음부터 켜져 있어서 모든 사용자에게 뜬다. 관리자가 끄면 바로 안 뜬다
- 계정 하나당 한 번만. 답하면 다시 안 뜬다
- 찬성/반대를 꼭 골라야 한다. 하고 싶은 말은 선택
- 지난 설문(2026-11-feedback)에 답한 사람에게도 이 설문은 한 번 뜬다
- 관리자 결과 화면: 찬성/반대 수, 성별·지금 찾는 관계별, 하고 싶은 말
"""

from app.models.admin import AuditLog
from app.models.survey import SurveyResponse
from app.models.user import User
from tests.conftest import admin_login, signup


def open_survey(admin, on=True):
    r = admin.put("/api/v1/admin/survey/open", json={"open": on})
    assert r.status_code == 200, r.text


SURVEY_HEADER = {"X-Survey-Version": "2026-11-friend-goal"}


def pending(client) -> bool:
    return client.get("/api/v1/me", headers=SURVEY_HEADER).json()["survey"]["pending"]


def test_old_screen_does_not_get_survey(sent_codes, db):
    """2026-11-22 버그: 예전 화면이 옛 설문을 띄움 → 지금 설문을 아는 화면(머리말)에만 pending."""
    admin_login(db)
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    assert a.get("/api/v1/me").json()["survey"] == {"pending": False, "key": "2026-11-friend-goal"}
    assert a.get("/api/v1/me", headers={"X-Survey-Version": "2026-11-feedback"}).json()["survey"]["pending"] is False
    assert pending(a) is True


def test_survey_shows_to_everyone_by_default(sent_codes, db):
    admin = admin_login(db)
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    assert pending(a) is True  # 관리자가 켜지 않아도 뜬다
    open_survey(admin, False)
    assert pending(a) is False
    assert a.post("/api/v1/me/survey", json={"vote": "AGREE"}).status_code == 409  # 받는 중이 아님
    open_survey(admin)
    assert pending(a) is True
    assert [l.action for l in db.query(AuditLog).filter(AuditLog.target_type == "SURVEY")] == ["SURVEY_CLOSE", "SURVEY_OPEN"]


def test_vote_once_per_account(sent_codes, db):
    admin = admin_login(db)
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    r = a.post("/api/v1/me/survey", json={"vote": "AGREE", "comment": "  친구는 다른 앱으로  "})
    assert r.status_code == 201, r.text
    assert pending(a) is False
    assert a.get("/api/v1/me/survey").json() == {"open": True, "answered": True, "pending": False}
    assert a.post("/api/v1/me/survey", json={"vote": "DISAGREE"}).status_code == 409
    row = db.query(SurveyResponse).one()
    assert row.survey_key == "2026-11-friend-goal"
    assert row.vote == "AGREE" and row.suggestion == "친구는 다른 앱으로"
    # 껐다 다시 켜도 답한 사람에게는 안 뜬다
    open_survey(admin, False)
    open_survey(admin)
    assert pending(a) is False


def test_vote_required(sent_codes, db):
    admin_login(db)
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    assert a.post("/api/v1/me/survey", json={}).status_code == 422
    assert a.post("/api/v1/me/survey", json={"vote": "MAYBE"}).status_code == 422
    assert a.post("/api/v1/me/survey", json={"comment": "의견만"}).status_code == 422
    assert a.post("/api/v1/me/survey", json={"vote": "DISAGREE", "comment": "가" * 1001}).status_code == 422
    assert pending(a) is True
    assert a.post("/api/v1/me/survey", json={"vote": "DISAGREE", "comment": "   "}).status_code == 201
    assert db.query(SurveyResponse).one().suggestion is None


def test_old_survey_answer_does_not_count(sent_codes, db):
    """지난 설문에 답한 사람에게도 이 설문은 뜬다."""
    admin = admin_login(db)
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    user = db.query(User).filter(User.email == "a@hufs.ac.kr").one()
    db.add(SurveyResponse(user_id=user.id, survey_key="2026-11-feedback", improvement="예전 의견"))
    db.commit()
    assert pending(a) is True
    assert a.post("/api/v1/me/survey", json={"vote": "AGREE"}).status_code == 201
    assert pending(a) is False
    assert admin.get("/api/v1/admin/survey").json()["total"] == 1


def test_admin_results(sent_codes, db):
    admin = admin_login(db)
    m = signup(sent_codes, db, "m@hufs.ac.kr", gender="MALE")
    f = signup(sent_codes, db, "f@hufs.ac.kr", gender="FEMALE")
    s = signup(sent_codes, db, "s@hufs.ac.kr", gender="FEMALE")
    assert m.patch("/api/v1/me/profile", json={"relationship_goal": "FRIEND"}).status_code == 200
    m.post("/api/v1/me/survey", json={"vote": "DISAGREE", "comment": "친구 찾고 싶어요"})
    f.post("/api/v1/me/survey", json={"vote": "AGREE"})
    s.post("/api/v1/me/survey", json={"vote": "AGREE"})

    body = admin.get("/api/v1/admin/survey").json()
    assert body["open"] is True and body["total"] == 3
    assert body["votes"] == {"AGREE": 2, "DISAGREE": 1}
    assert body["by_gender"] == {"MALE": {"AGREE": 0, "DISAGREE": 1}, "FEMALE": {"AGREE": 2, "DISAGREE": 0}}
    assert body["by_goal"]["FRIEND"] == {"AGREE": 0, "DISAGREE": 1}
    assert body["by_goal"]["NONE"] == {"AGREE": 2, "DISAGREE": 0}
    assert [(c["vote"], c["gender"], c["goal"], c["comment"]) for c in body["comments"]] == [
        ("DISAGREE", "MALE", "FRIEND", "친구 찾고 싶어요")
    ]
    assert "email" not in str(body) and "nickname" not in str(body)


def test_survey_admin_permission(sent_codes, db):
    mod = admin_login(db, role="MODERATOR")
    assert mod.get("/api/v1/admin/survey").status_code == 403
    assert mod.put("/api/v1/admin/survey/open", json={"open": True}).status_code == 403
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    assert a.get("/api/v1/admin/survey").status_code == 401
