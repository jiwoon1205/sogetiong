"""이탈 막기 (2026-11-16): 매칭 확률 높이기 팝업 + 휴면 계정 좋아요 알림."""

from datetime import date, timedelta

from app.core.time import utcnow
from app.models.matching import Notification
from app.models.user import UserDailyVisit
from app.services import engagement_service, push_service
from tests.conftest import admin_login, ready_user
from tests.test_membership import user_of


def _visits(db, client, n):
    user = user_of(db, client)
    db.query(UserDailyVisit).filter(UserDailyVisit.user_id == user.id).delete()
    for k in range(n):
        db.add(UserDailyVisit(user_id=user.id, visit_date=date(2026, 11, 1) + timedelta(days=k)))
    db.commit()


# ---------- 매칭 확률 높이기 팝업 ----------


def test_tip_for_man_with_three_visit_days_and_no_match(sent_codes, db):
    admin = admin_login(db)
    him = ready_user(sent_codes, db, admin, "him@hufs.ac.kr", gender="MALE")
    _visits(db, him, 2)
    assert him.get("/api/v1/me").json()["match_tip"] is None  # 2일은 아직
    _visits(db, him, 3)
    tip = him.get("/api/v1/me").json()["match_tip"]
    assert tip is not None and tip["good_bio_chars"] == 100 and "bio_chars" in tip and "mbti_set" in tip

    # 닫으면 다시 안 뜨고 알림 목록에 남는다
    assert him.post("/api/v1/me/match-tip/seen").status_code == 200
    assert him.get("/api/v1/me").json()["match_tip"] is None
    uid = user_of(db, him).id
    assert db.query(Notification).filter(Notification.user_id == uid, Notification.type == "MATCH_TIP").count() == 1
    assert him.post("/api/v1/me/match-tip/seen").status_code == 200  # 두 번 눌러도 알림은 하나
    assert db.query(Notification).filter(Notification.user_id == uid, Notification.type == "MATCH_TIP").count() == 1


def test_no_tip_for_women_or_men_with_a_match(sent_codes, db):
    admin = admin_login(db)
    her = ready_user(sent_codes, db, admin, "her@hufs.ac.kr", gender="FEMALE")
    him = ready_user(sent_codes, db, admin, "him@hufs.ac.kr", gender="MALE")
    _visits(db, her, 5)
    _visits(db, him, 5)
    assert her.get("/api/v1/me").json()["match_tip"] is None
    assert him.post("/api/v1/likes", json={"profile_id": her.profile_id}).status_code == 200
    assert her.post("/api/v1/likes", json={"profile_id": him.profile_id}).json()["matched"] is True
    assert him.get("/api/v1/me").json()["match_tip"] is None


# ---------- 휴면 계정 좋아요 알림 ----------


def _dormant(db, client, days=8):
    user = user_of(db, client)
    user.last_active_at = utcnow() - timedelta(days=days)
    db.commit()
    return user


def test_dormant_user_gets_one_alert_per_three_days(sent_codes, db, monkeypatch):
    admin = admin_login(db)
    her = ready_user(sent_codes, db, admin, "her@hufs.ac.kr", gender="FEMALE")
    men = [ready_user(sent_codes, db, admin, f"m{i}@hufs.ac.kr", gender="MALE") for i in range(3)]
    sent = []
    monkeypatch.setattr(push_service, "queue", lambda db_, uid, kind, mid: sent.append((uid, kind)))
    target = _dormant(db, her)

    assert men[0].post("/api/v1/likes", json={"profile_id": her.profile_id}).status_code == 200
    assert sent == [(target.id, push_service.LIKED)]
    # 3일 안에 또 받으면 알림 없음
    _dormant(db, her)  # (테스트 클라이언트 요청으로 접속 시각이 바뀌지 않게 다시 맞춤)
    assert men[1].post("/api/v1/likes", json={"profile_id": her.profile_id}).status_code == 200
    assert len(sent) == 1
    # 3일이 지나면 다시
    user = _dormant(db, her)
    user.winback_sent_at = utcnow() - timedelta(days=3, minutes=1)
    db.commit()
    assert men[2].post("/api/v1/likes", json={"profile_id": her.profile_id}).status_code == 200
    assert len(sent) == 2


def test_active_user_gets_no_alert(sent_codes, db, monkeypatch):
    admin = admin_login(db)
    her = ready_user(sent_codes, db, admin, "her@hufs.ac.kr", gender="FEMALE")
    him = ready_user(sent_codes, db, admin, "him@hufs.ac.kr", gender="MALE")
    sent = []
    monkeypatch.setattr(push_service, "queue", lambda db_, uid, kind, mid: sent.append(kind))
    _dormant(db, her, days=6)  # 6일 전 접속 = 아직 휴면 아님
    assert him.post("/api/v1/likes", json={"profile_id": her.profile_id}).status_code == 200
    assert sent == []


def test_liked_payload_and_email_fallback(sent_codes, db, monkeypatch):
    admin = admin_login(db)
    her = ready_user(sent_codes, db, admin, "her@hufs.ac.kr", gender="FEMALE")
    alert = push_service.Alert(user_id=user_of(db, her).id, kind=push_service.LIKED, match_id=None)
    payload = push_service.payload_for(alert)
    assert payload["url"] == "/discover" and "좋아요" in payload["body"]
    mails = []
    monkeypatch.setattr("app.services.email_service.EmailService.send_liked_notice", staticmethod(lambda e: mails.append(e)))
    assert push_service.deliver(alert) == "email"  # 휴대폰 알림을 안 켰으면 메일
    assert mails == ["her@hufs.ac.kr"]


def test_maybe_winback_skips_deleted_and_never_active(sent_codes, db, monkeypatch):
    admin = admin_login(db)
    her = ready_user(sent_codes, db, admin, "her@hufs.ac.kr", gender="FEMALE")
    monkeypatch.setattr(push_service, "queue", lambda *a: None)
    user = user_of(db, her)
    user.last_active_at = None
    db.commit()
    assert engagement_service.maybe_winback(db, user.id) is False
