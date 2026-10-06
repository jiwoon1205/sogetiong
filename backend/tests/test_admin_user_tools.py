"""관리자 사용자 관리 도구 (2026-10-06).

1) 사용자 목록 검색칸 하나(q)로 닉네임 또는 사용자 코드(예: UA38192)를 찾는다.
   코드는 DB에 없고 ID에서 계산하므로 서버가 사람마다 계산해서 비교한다. 대소문자·일부만 입력해도 된다.
2) 관리자가 VIP 기간을 늘리거나 줄인다 (이용권 기간 조정과 같은 규칙, 감사 로그 VIP_ADJUST).
"""

import uuid
from datetime import timedelta

from app.core.time import as_utc, utcnow
from app.models.admin import AuditLog
from app.models.user import User

from tests.conftest import admin_login, signup


def _users(admin, query=""):
    return admin.get("/api/v1/admin/users" + query).json()["users"]


def test_search_by_user_code_or_nickname(sent_codes, db):
    signup(sent_codes, db, "a@hufs.ac.kr")
    signup(sent_codes, db, "b@hufs.ac.kr")
    admin = admin_login(db)
    rows = _users(admin)
    assert len(rows) == 2
    target = rows[0]
    code = target["subject_code"]

    for q in [code, code.lower(), code[1:5]]:  # 전체 코드 / 소문자 / 일부
        found = _users(admin, f"?q={q}")
        assert target["user_id"] in [u["user_id"] for u in found], q

    by_nick = _users(admin, f"?q={target['nickname']}")
    assert [u["user_id"] for u in by_nick] == [target["user_id"]]

    assert _users(admin, "?q=없는사람xyz") == []
    # 예전 닉네임 전용 검색도 그대로 된다
    assert [u["user_id"] for u in _users(admin, f"?nickname={target['nickname']}")] == [target["user_id"]]


def _user(db, uid) -> User:
    db.expire_all()
    return db.get(User, uuid.UUID(uid))


def test_admin_can_extend_and_shorten_vip(sent_codes, db):
    signup(sent_codes, db, "a@hufs.ac.kr")
    admin = admin_login(db)
    uid = _users(admin)[0]["user_id"]
    url = f"/api/v1/admin/users/{uid}/vip-adjust"

    # VIP가 없던 사람: 지금부터 3일 (그날 밤 12시까지)
    r = admin.post(url, json={"days": 3, "reason": "서버 장애 보상"})
    assert r.status_code == 200, r.text
    assert r.json()["vip_active"] is True
    first = as_utc(_user(db, uid).vip_until)
    assert timedelta(days=3) <= first - utcnow() <= timedelta(days=4)

    # 남아 있으면 끝나는 날에서 더하고 뺀다
    assert admin.post(url, json={"days": 5, "reason": "보상"}).status_code == 200
    assert as_utc(_user(db, uid).vip_until) == first + timedelta(days=5)
    assert admin.post(url, json={"days": -2, "reason": "정정"}).status_code == 200
    assert as_utc(_user(db, uid).vip_until) == first + timedelta(days=3)

    # 0일은 거절, 감사 로그는 3번
    assert admin.post(url, json={"days": 0, "reason": "보상"}).status_code == 400
    logs = db.query(AuditLog).filter(AuditLog.action == "VIP_ADJUST").count()
    assert logs == 3

    # 상세 화면에 바뀐 VIP 끝 시각이 나온다
    detail = admin.get(f"/api/v1/admin/users/{uid}").json()
    assert detail["vip_until"] is not None


def test_shortening_vip_without_vip_does_nothing(sent_codes, db):
    signup(sent_codes, db, "a@hufs.ac.kr")
    admin = admin_login(db)
    uid = _users(admin)[0]["user_id"]
    r = admin.post(f"/api/v1/admin/users/{uid}/vip-adjust", json={"days": -3, "reason": "정정"})
    assert r.status_code == 200
    assert _user(db, uid).vip_until is None


def test_vip_adjust_needs_payment_permission(sent_codes, db):
    signup(sent_codes, db, "a@hufs.ac.kr")
    admin = admin_login(db)
    uid = _users(admin)[0]["user_id"]
    reviewer = admin_login(db, role="MODERATOR")
    r = reviewer.post(f"/api/v1/admin/users/{uid}/vip-adjust", json={"days": 3, "reason": "보상"})
    assert r.status_code == 403


def test_membership_filter_matches_dashboard_counts(sent_codes, db):
    """현황의 '이용권 이용 중' 칸을 누르면 나오는 목록 = 그 칸의 숫자 (2026-10-06)."""
    for e in ["a@hufs.ac.kr", "b@hufs.ac.kr", "c@hufs.ac.kr", "d@hufs.ac.kr"]:
        signup(sent_codes, db, e)
    admin = admin_login(db)
    ids = {u["nickname"]: u["user_id"] for u in _users(admin)}
    a, b, c, d = (uuid.UUID(i) for i in ids.values())
    now = utcnow()
    db.get(User, a).member_until = now + timedelta(days=20)  # 이용 중
    db.get(User, b).member_until = now + timedelta(days=3)  # 7일 안에 끝남
    db.get(User, b).vip_until = now + timedelta(days=3)  # VIP
    db.get(User, c).member_until = now - timedelta(days=1)  # 끝남
    db.commit()

    def got(m):
        return [uuid.UUID(u["user_id"]) for u in _users(admin, f"?membership={m}")]

    assert got("active") == [b, a]  # 곧 끝나는 사람부터
    assert got("vip") == [b]
    assert got("expiring") == [b]
    stats = admin.get("/api/v1/admin/dashboard").json()
    assert stats["members_active"] == 2 and stats["members_vip"] == 1 and stats["members_expiring_week"] == 1

    row = next(u for u in _users(admin, "?membership=active") if uuid.UUID(u["user_id"]) == a)
    assert row["member_until"] is not None and row["vip_until"] is None
    assert admin.get("/api/v1/admin/users?membership=nope").status_code == 422
