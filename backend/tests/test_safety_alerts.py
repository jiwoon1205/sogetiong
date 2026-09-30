"""끝난 대화 신고(A-13), 운영진 알림 메일(A-14, 사진 10장), 사진 결과 메일, 검수 대기열."""

import pytest

from app.core.config import get_settings
from app.models import User
from tests.conftest import admin_login, approve, ready_user, signup, upload_photo


@pytest.fixture
def mails(monkeypatch):
    """보낸 메일을 실제로 보내지 않고 (종류, 받는 사람, 내용) 목록에 모아둔다."""
    box: list[tuple] = []
    base = "app.services.email_service.EmailService."
    monkeypatch.setattr(base + "send_photo_approved", staticmethod(lambda email: box.append(("approved", email))))
    monkeypatch.setattr(base + "send_photo_rejected", staticmethod(lambda email, reason: box.append(("rejected", email, reason))))
    monkeypatch.setattr(base + "send_admin_photo_queue", staticmethod(lambda email, n: box.append(("photo_queue", email, n))))
    monkeypatch.setattr(base + "send_admin_new_report", staticmethod(lambda email, reason: box.append(("report", email, reason))))
    return box


def _match(a, b) -> str:
    a.post("/api/v1/likes", json={"profile_id": b.profile_id})
    return b.post("/api/v1/likes", json={"profile_id": a.profile_id}).json()["match_id"]


# ---------- A-13: 끝난 대화 신고 ----------

def test_can_report_partner_who_deleted_account(sent_codes, db, mails):
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr", gender="FEMALE")
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr", gender="MALE")
    match_id = _match(a, b)
    b.post(f"/api/v1/matches/{match_id}/messages", json={"body": "나쁜 말"})

    # 상대가 탈퇴 → 공개 프로필이 사라짐 → 예전 방식(profile_id)으로는 신고 불가
    assert b.delete("/api/v1/me", json={"password": "goodpass123"}).status_code == 200
    assert a.post("/api/v1/reports", json={"profile_id": b.profile_id, "reason": "ABUSIVE_LANGUAGE"}).status_code == 404

    # 끝난 대화 목록에 "탈퇴한 사용자"로 보인다
    ended = a.get("/api/v1/matches/ended").json()["matches"]
    assert [(m["match_id"], m["partner_nickname"], m["report_pending"]) for m in ended] == [(match_id, "탈퇴한 사용자", False)]

    # 대화방 기준으로는 신고 가능
    r = a.post("/api/v1/reports", json={"match_id": match_id, "reason": "ABUSIVE_LANGUAGE", "description": "욕설"})
    assert r.status_code == 201, r.text
    assert a.get("/api/v1/matches/ended").json()["matches"][0]["report_pending"] is True
    assert a.post("/api/v1/reports", json={"match_id": match_id, "reason": "SPAM"}).status_code == 409

    # 관리자 화면에서 신고 + 대화 내용 확인 가능, 신고 담당자에게 메일
    reports = admin.get("/api/v1/admin/reports").json()["reports"]
    assert reports[0]["match_id"] == match_id
    assert admin.get(f"/api/v1/admin/matches/{match_id}/messages").json()["messages"][0]["body"] == "나쁜 말"
    assert ("report", "super_admin@test.com", "ABUSIVE_LANGUAGE") in mails


def test_report_after_block_and_unmatch(sent_codes, db, mails):
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr", gender="FEMALE")
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr", gender="MALE")
    match_id = _match(a, b)
    a.post("/api/v1/blocks", json={"profile_id": b.profile_id})
    # 차단한 뒤에도 그 대화방으로 신고할 수 있다
    assert a.post("/api/v1/reports", json={"match_id": match_id, "reason": "THREAT"}).status_code == 201
    # 차단당한 쪽의 끝난 대화 목록에는 이유(차단)가 드러나지 않는다
    ended_b = b.get("/api/v1/matches/ended").json()["matches"]
    assert set(ended_b[0]) == {"match_id", "partner_nickname", "matched_at", "ended_at", "report_pending"}


def test_cannot_report_through_someone_elses_match(sent_codes, db, mails):
    admin = admin_login(db)
    a = ready_user(sent_codes, db, admin, "a@hufs.ac.kr", gender="FEMALE")
    b = ready_user(sent_codes, db, admin, "b@hufs.ac.kr", gender="MALE")
    c = ready_user(sent_codes, db, admin, "c@hufs.ac.kr", gender="MALE")
    match_id = _match(a, b)
    assert c.post("/api/v1/reports", json={"match_id": match_id, "reason": "SPAM"}).status_code == 400
    # 대화방과 다른 사람의 profile_id를 같이 보내면 거절
    assert a.post("/api/v1/reports", json={"match_id": match_id, "profile_id": c.profile_id, "reason": "SPAM"}).status_code == 400
    # 대상이 없으면 거절
    assert a.post("/api/v1/reports", json={"reason": "SPAM"}).status_code == 422
    assert c.get("/api/v1/matches/ended").json()["matches"] == []


# ---------- 사진 검수 ----------

def test_photo_backlog_alert_every_10_pending(sent_codes, db, mails, monkeypatch):
    monkeypatch.setattr(get_settings(), "photo_alert_threshold", 3)
    admin = admin_login(db)
    admin_login(db, "PHOTO_REVIEWER")
    admin_login(db, "MODERATOR")  # 사진 권한 없음 → 메일 안 받음
    users = [signup(sent_codes, db, f"p{i}@hufs.ac.kr") for i in range(5)]
    photos = [upload_photo(users[i]) for i in range(2)]
    assert [m for m in mails if m[0] == "photo_queue"] == []  # 2장: 아직

    photos.append(upload_photo(users[2]))  # 3장: 알림
    queue = sorted(m for m in mails if m[0] == "photo_queue")
    assert queue == [("photo_queue", "photo_reviewer@test.com", 3), ("photo_queue", "super_admin@test.com", 3)]

    photos.append(upload_photo(users[3]))  # 4장: 이미 보냈으니 또 안 보냄
    assert len([m for m in mails if m[0] == "photo_queue"]) == 2

    # 검수해서 기준 아래(2장)로 줄면 → 다시 3장이 될 때 또 보냄
    approve(admin, photos[0])
    approve(admin, photos[1])
    upload_photo(users[4])
    assert len([m for m in mails if m[0] == "photo_queue"]) == 4


def test_photo_result_emails_to_user(sent_codes, db, mails):
    admin = admin_login(db)
    u = signup(sent_codes, db, "u@hufs.ac.kr")
    p1 = upload_photo(u)
    r = admin.put(f"/api/v1/admin/photo-reviews/{p1}/evaluation", json={"decision": "REJECTED", "reject_reason": "얼굴이 안 보여요"})
    assert r.status_code == 200
    assert ("rejected", "u@hufs.ac.kr", "얼굴이 안 보여요") in mails
    approve(admin, upload_photo(u))
    assert ("approved", "u@hufs.ac.kr") in mails


def test_queue_keeps_opened_photos_and_skips_suspended_users(sent_codes, db, mails):
    admin = admin_login(db)
    a = signup(sent_codes, db, "a@hufs.ac.kr")
    b = signup(sent_codes, db, "b@hufs.ac.kr")
    pa = upload_photo(a)
    pb = upload_photo(b)

    # 상세를 열기만 하고 평가를 안 끝내도 대기열에 남는다 ("확인 중"으로 표시)
    admin.get(f"/api/v1/admin/photo-reviews/{pa}")
    queue = {p["photo_id"]: p["review_status"] for p in admin.get("/api/v1/admin/photo-reviews?status=PENDING").json()["photos"]}
    assert queue == {pa: "IN_REVIEW", pb: "PENDING"}

    # 정지된 사용자의 사진은 대기열·대시보드에서 빠진다
    b_id = db.query(User).filter(User.email == "b@hufs.ac.kr").one().id
    r = admin.patch(f"/api/v1/admin/users/{b_id}/status", json={"status": "SUSPENDED", "reason": "테스트"})
    assert r.status_code == 200, r.text
    queue = [p["photo_id"] for p in admin.get("/api/v1/admin/photo-reviews?status=PENDING").json()["photos"]]
    assert queue == [pa]
    assert admin.get("/api/v1/admin/dashboard").json()["photos_pending"] == 1
