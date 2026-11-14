"""사용자 설문 (2026-10-05, 2026-11-14 개선점·바라는 기능 설문으로 교체).

- 관리자가 켜야 뜬다. 끄면 바로 안 뜬다
- 계정 하나당 한 번만. 답하거나 건너뛰면 다시 안 뜬다
- 두 질문 중 하나 이상 적어야 제출된다. 쓸 말이 없으면 "건너뛰기"
- 옛 설문(2026-10-launch)에 답한 사람에게도 새 설문은 한 번 뜬다
- 관리자 결과 화면: 응답 수(성별), 적은 사람·건너뛴 사람 수, 적은 글
"""

from app.models.admin import AuditLog
from app.models.survey import SurveyResponse
from app.models.user import User
from tests.conftest import admin_login, signup

ANSWER = {
    "improvement": "  추천이 더 다양했으면  ",
    "feature_request": "",
}


def open_survey(admin, on=True):
    r = admin.put("/api/v1/admin/survey/open", json={"open": on})
    assert r.status_code == 200, r.text


def pending(client) -> bool:
    return client.get("/api/v1/me").json()["survey"]["pending"]


def test_survey_hidden_until_admin_opens(sent_codes, db):
    admin = admin_login(db)
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    assert pending(a) is False
    assert a.post("/api/v1/me/survey", json=ANSWER).status_code == 409  # 받는 중이 아님

    open_survey(admin)
    assert pending(a) is True
    open_survey(admin, False)
    assert pending(a) is False
    assert [l.action for l in db.query(AuditLog).filter(AuditLog.target_type == "SURVEY")] == ["SURVEY_OPEN", "SURVEY_CLOSE"]


def test_answer_once_per_account(sent_codes, db):
    admin = admin_login(db)
    open_survey(admin)
    a = signup(sent_codes, db, "a@hufs.ac.kr")

    r = a.post("/api/v1/me/survey", json=ANSWER)
    assert r.status_code == 201, r.text
    assert pending(a) is False
    assert a.get("/api/v1/me/survey").json() == {"open": True, "answered": True, "pending": False}

    # 두 번째는 안 된다
    assert a.post("/api/v1/me/survey", json={"feature_request": "또"}).status_code == 409
    row = db.query(SurveyResponse).one()
    assert row.survey_key == "2026-11-feedback"
    assert row.improvement == "추천이 더 다양했으면"  # 앞뒤 공백 정리
    assert row.feature_request is None  # 빈 글은 저장하지 않음
    assert row.appearance_choice is None and row.payment_rating is None  # 옛 질문은 없음

    # 껐다 다시 켜도 답한 사람에게는 안 뜬다
    open_survey(admin, False)
    open_survey(admin)
    assert pending(a) is False


def test_needs_some_text_or_skip(sent_codes, db):
    admin = admin_login(db)
    open_survey(admin)
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    # 둘 다 비어 있으면 안 됨
    assert a.post("/api/v1/me/survey", json={"improvement": "  ", "feature_request": ""}).status_code == 422
    assert a.post("/api/v1/me/survey", json={}).status_code == 422
    # 너무 긴 글
    assert a.post("/api/v1/me/survey", json={"improvement": "가" * 1001}).status_code == 422
    assert pending(a) is True

    # 건너뛰기: 적은 글이 있어도 저장하지 않고, 다시 안 뜬다
    r = a.post("/api/v1/me/survey", json={"skip": True, "improvement": "저장 안 됨"})
    assert r.status_code == 201, r.text
    assert pending(a) is False
    row = db.query(SurveyResponse).one()
    assert row.improvement is None and row.feature_request is None


def test_old_survey_answer_does_not_count(sent_codes, db):
    """옛 설문(정식 오픈 전)에 답한 사람에게도 새 설문은 뜬다."""
    admin = admin_login(db)
    open_survey(admin)
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    user = db.query(User).filter(User.email == "a@hufs.ac.kr").one()
    db.add(SurveyResponse(user_id=user.id, survey_key="2026-10-launch", appearance_choice="AI_ONLY", payment_rating=4))
    db.commit()
    assert pending(a) is True
    assert a.post("/api/v1/me/survey", json={"feature_request": "프로필 꾸미기"}).status_code == 201
    assert pending(a) is False
    # 관리자 결과에는 새 설문만
    assert admin.get("/api/v1/admin/survey").json()["total"] == 1


def test_admin_results(sent_codes, db):
    admin = admin_login(db)
    open_survey(admin)
    m = signup(sent_codes, db, "m@hufs.ac.kr", gender="MALE")
    f = signup(sent_codes, db, "f@hufs.ac.kr", gender="FEMALE")
    s = signup(sent_codes, db, "s@hufs.ac.kr", gender="FEMALE")
    m.post("/api/v1/me/survey", json={"improvement": "로딩이 느려요"})
    f.post("/api/v1/me/survey", json={"improvement": "", "feature_request": "채팅에 사진 보내기"})
    s.post("/api/v1/me/survey", json={"skip": True})

    r = admin.get("/api/v1/admin/survey")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["open"] is True and body["total"] == 3
    assert body["by_gender"] == {"MALE": 1, "FEMALE": 2}
    assert body["written"] == 2 and body["skipped"] == 1
    texts = {(x["gender"], x["improvement"], x["feature_request"]) for x in body["responses"]}
    assert texts == {("MALE", "로딩이 느려요", None), ("FEMALE", None, "채팅에 사진 보내기")}
    # 개인 식별 정보는 내보내지 않는다
    assert "email" not in str(body) and "nickname" not in str(body)


def test_survey_admin_permission(sent_codes, db):
    mod = admin_login(db, role="MODERATOR")
    assert mod.get("/api/v1/admin/survey").status_code == 403
    assert mod.put("/api/v1/admin/survey/open", json={"open": True}).status_code == 403
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    assert a.get("/api/v1/admin/survey").status_code == 401
