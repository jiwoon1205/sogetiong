"""사용자 설문 (2026-10-05).

- 관리자가 켜야 뜬다. 끄면 바로 안 뜬다
- 계정 하나당 한 번만. 답하면 다시 안 뜬다
- '기타'는 내용을 꼭 적어야 한다
- 관리자 결과 화면: 보기별 개수(성별 포함), 만족도 평균, 적은 글
"""

from app.models.admin import AuditLog
from app.models.survey import SurveyResponse
from tests.conftest import admin_login, signup

ANSWER = {
    "appearance_choice": "AI_PLUS_ADMIN",
    "payment_rating": 4,
    "payment_comment": "  가격 괜찮아요  ",
    "suggestion": "",
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
    assert a.post("/api/v1/me/survey", json={**ANSWER, "payment_rating": 1}).status_code == 409
    row = db.query(SurveyResponse).one()
    assert row.payment_rating == 4
    assert row.payment_comment == "가격 괜찮아요"  # 앞뒤 공백 정리
    assert row.suggestion is None  # 빈 글은 저장하지 않음

    # 껐다 다시 켜도 답한 사람에게는 안 뜬다
    open_survey(admin, False)
    open_survey(admin)
    assert pending(a) is False


def test_validation(sent_codes, db):
    admin = admin_login(db)
    open_survey(admin)
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    # '기타'인데 내용 없음
    assert a.post("/api/v1/me/survey", json={**ANSWER, "appearance_choice": "OTHER", "appearance_comment": "  "}).status_code == 422
    # 만족도 범위 밖
    assert a.post("/api/v1/me/survey", json={**ANSWER, "payment_rating": 6}).status_code == 422
    # 없는 보기
    assert a.post("/api/v1/me/survey", json={**ANSWER, "appearance_choice": "NOPE"}).status_code == 422
    assert pending(a) is True

    # 1번 '적는 칸'은 2번(기준 변경)·5번(기타)일 때만 저장
    r = a.post("/api/v1/me/survey", json={**ANSWER, "appearance_choice": "AI_ONLY", "appearance_comment": "남은 글"})
    assert r.status_code == 201
    assert db.query(SurveyResponse).one().appearance_comment is None


def test_admin_results(sent_codes, db):
    admin = admin_login(db)
    open_survey(admin)
    m = signup(sent_codes, db, "m@hufs.ac.kr", gender="MALE")
    f = signup(sent_codes, db, "f@hufs.ac.kr", gender="FEMALE")
    m.post("/api/v1/me/survey", json={**ANSWER, "appearance_choice": "OTHER", "appearance_comment": "투표로", "payment_rating": 2})
    f.post("/api/v1/me/survey", json={**ANSWER, "payment_rating": 5, "suggestion": "채팅 알림이 있었으면"})

    r = admin.get("/api/v1/admin/survey")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["open"] is True and body["total"] == 2
    assert body["by_gender"] == {"MALE": 1, "FEMALE": 1}
    counts = {row["key"]: (row["total"], row["MALE"], row["FEMALE"]) for row in body["appearance"]}
    assert counts["OTHER"] == (1, 1, 0) and counts["AI_PLUS_ADMIN"] == (1, 0, 1) and counts["AI_ONLY"] == (0, 0, 0)
    assert body["payment_average"] == 3.5
    texts = {(x["gender"], x["appearance_comment"], x["suggestion"]) for x in body["responses"]}
    assert ("MALE", "투표로", None) in texts and ("FEMALE", None, "채팅 알림이 있었으면") in texts
    # 개인 식별 정보는 내보내지 않는다
    assert "email" not in str(body) and "nickname" not in str(body)


def test_survey_admin_permission(sent_codes, db):
    mod = admin_login(db, role="MODERATOR")
    assert mod.get("/api/v1/admin/survey").status_code == 403
    assert mod.put("/api/v1/admin/survey/open", json={"open": True}).status_code == 403
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    assert a.get("/api/v1/admin/survey").status_code == 401
