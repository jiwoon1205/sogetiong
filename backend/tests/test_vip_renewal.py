"""VIP 재구매 할인·연장 알림 (2026-11-12) + 가입 선물 슈퍼 라이크 (2026-11-12).

- VIP를 산 적 있는 사람이 VIP가 끝나기 3일 전 ~ 끝난 뒤 3일 안에 다시 사면 1,000원 할인 (남녀 같음)
- 끝나기 전에도 그 3일 안에는 연장할 수 있고, 새 VIP는 지금 VIP가 끝난 뒤에 이어진다
- 관리자 결제 목록에 renewal_discount가 보인다 ("재구매")
- 알림: 끝나기 2일 전 "곧 끝나요", 끝난 뒤 "끝났어요" (한국 시간 9~22시, 한 번씩)
- 처음 가입한 사람은 슈퍼 라이크 1개 (탈퇴 후 재가입은 제외)
"""

from datetime import timedelta

import pytest

from app.core.time import KST, as_utc, utcnow
from app.models.matching import Notification
from app.services import vip_service
from tests.conftest import admin_login, ready_user
from tests.test_membership import paid_world, pay, switch_on, user_of  # noqa: F401  (paid_world는 fixture)


@pytest.fixture
def vip_world(monkeypatch, paid_world):
    switch_on(monkeypatch, paid_world, vip=True)
    return paid_world


def _set_vip_end(db, client, delta: timedelta):
    user = user_of(db, client)
    user.vip_until = utcnow() + delta
    db.commit()
    return user


def test_renewal_discount_window(sent_codes, db, vip_world):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE")
    # 처음 사는 VIP는 할인 없음
    vip = me.get("/api/v1/me/vip").json()
    assert vip["price"] == 6000 and vip["renewal"] is None and vip["renewal_discount_amount"] == 1000
    pay(admin, me, "vip")

    # VIP가 10일 남음 → 아직 연장할 수 없다
    _set_vip_end(db, me, timedelta(days=10))
    vip = me.get("/api/v1/me/vip").json()
    assert vip["can_buy"] is False and "3일 전부터" in vip["blocked_reason"]

    # 끝나기 2일 전 → 연장 가능, 5,000원
    _set_vip_end(db, me, timedelta(days=2))
    vip = me.get("/api/v1/me/vip").json()
    assert vip["can_buy"] is True and vip["price"] == 5000 and vip["base_price"] == 6000
    assert vip["renewal"]["discount"] == 1000 and vip["payment"]["amount"] == 5000

    # 끝난 지 2일 → 할인
    _set_vip_end(db, me, timedelta(days=-2))
    assert me.get("/api/v1/me/vip").json()["price"] == 5000

    # 끝난 지 4일 → 할인 없음 (아직 "입금했어요" 전인 결제 코드 금액도 다시 6,000원)
    _set_vip_end(db, me, timedelta(days=-4))
    vip = me.get("/api/v1/me/vip").json()
    assert vip["price"] == 6000 and vip["renewal"] is None and vip["payment"]["amount"] == 6000


def test_renew_before_end_extends_after_current_vip(sent_codes, db, vip_world):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE")
    pay(admin, me, "vip")
    old_end = as_utc(_set_vip_end(db, me, timedelta(days=1)).vip_until)

    assert me.post("/api/v1/me/vip/request").status_code == 200
    row = next(p for p in admin.get("/api/v1/admin/payments").json()["payments"] if p["status"] == "REQUESTED")
    assert row["kind"] == "VIP" and row["amount"] == 5000 and row["renewal_discount"] == 1000  # 관리자 화면 "재구매"
    assert admin.post(f"/api/v1/admin/payments/{row['payment_id']}/confirm").status_code == 200

    user = user_of(db, me)
    assert as_utc(user.vip_until) >= old_end + timedelta(days=13)  # 지금 VIP 뒤에 14일이 이어진다
    titles = [n.title for n in db.query(Notification).filter(Notification.user_id == user.id)]
    assert "VIP가 연장되었어요" in titles


def test_first_vip_payment_is_not_renewal(sent_codes, db, vip_world):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE")
    assert me.post("/api/v1/me/vip/request").status_code == 200
    row = next(p for p in admin.get("/api/v1/admin/payments").json()["payments"] if p["status"] == "REQUESTED")
    assert row["renewal_discount"] == 0 and row["amount"] == 6000


def test_women_get_same_discount(sent_codes, db, vip_world, monkeypatch):
    monkeypatch.setattr(vip_world, "female_free", True)
    admin = admin_login(db)
    her = ready_user(sent_codes, db, admin, "her@hufs.ac.kr", gender="FEMALE")
    pay(admin, her, "vip")
    _set_vip_end(db, her, timedelta(days=-1))
    vip = her.get("/api/v1/me/vip").json()
    assert vip["price"] == 3000 and vip["base_price"] == 4000


def test_vip_without_payment_gets_no_discount(sent_codes, db, vip_world):
    """관리자가 준 VIP·여성 전환 VIP처럼 돈을 내고 산 적이 없으면 할인 없음."""
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE")
    _set_vip_end(db, me, timedelta(days=-1))
    assert me.get("/api/v1/me/vip").json()["price"] == 6000


def test_reminders_once_per_stage_and_quiet_hours(sent_codes, db, vip_world, monkeypatch):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE")
    other = ready_user(sent_codes, db, admin, "other@hufs.ac.kr", gender="FEMALE")
    pay(admin, me, "vip")
    pay(admin, other, "vip")
    _set_vip_end(db, other, timedelta(days=10))  # 아직 멀었다 → 알림 없음
    user = _set_vip_end(db, me, timedelta(days=1, hours=12))
    pushed = []
    monkeypatch.setattr("app.services.push_service.queue", lambda db_, uid, kind, mid: pushed.append((uid, kind)))

    def at_hour(h):
        base = utcnow().astimezone(KST).replace(hour=h, minute=0, second=0, microsecond=0)
        return base.astimezone(utcnow().tzinfo)

    noon = at_hour(12)
    user.vip_until = noon + timedelta(days=1, hours=12)
    db.commit()
    assert vip_service.send_renewal_reminders(db, at_hour(3)) == 0  # 새벽에는 안 보낸다
    assert vip_service.send_renewal_reminders(db, noon) == 1
    assert vip_service.send_renewal_reminders(db, noon + timedelta(hours=1)) == 0  # 같은 단계는 한 번만
    assert pushed == [(user.id, "VIP_ENDING")]

    # 끝난 다음 날 → "끝났어요" 한 번
    after = noon + timedelta(days=2)
    assert vip_service.send_renewal_reminders(db, after) == 1
    assert vip_service.send_renewal_reminders(db, after + timedelta(hours=1)) == 0
    assert pushed[-1] == (user.id, "VIP_ENDED")
    titles = [n.title for n in db.query(Notification).filter(Notification.user_id == user.id, Notification.type == "VIP_RENEWAL")]
    assert sorted(titles) == ["VIP가 곧 끝나요", "VIP가 끝났어요"]

    # 할인 기간도 지나면 더 보내지 않는다
    assert vip_service.send_renewal_reminders(db, noon + timedelta(days=6)) == 0


def test_no_reminder_while_payment_waiting(sent_codes, db, vip_world, monkeypatch):
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE")
    pay(admin, me, "vip")
    _set_vip_end(db, me, timedelta(days=1))
    assert me.post("/api/v1/me/vip/request").status_code == 200  # "입금했어요" 누름
    monkeypatch.setattr("app.services.push_service.queue", lambda *a: None)
    noon = utcnow().astimezone(KST).replace(hour=12)
    assert vip_service.send_renewal_reminders(db, noon) == 0


def test_vip_push_payload_and_no_email():
    from app.services import push_service

    alert = push_service.Alert(user_id=None, kind=push_service.VIP_ENDING, match_id=None)
    payload = push_service.payload_for(alert)
    assert payload["url"] == "/liked" and "VIP" in payload["body"]


# ---------- 가입 선물 슈퍼 라이크 ----------


def test_signup_gift_super_like_first_signup_only(sent_codes, db, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "signup_super_likes", 1)
    admin = admin_login(db)
    me = ready_user(sent_codes, db, admin, "me@hufs.ac.kr", gender="MALE")
    user = user_of(db, me)
    assert user.super_likes == 1
    assert db.query(Notification).filter(Notification.user_id == user.id, Notification.type == "SUPER_LIKE_GIFT").count() == 1

    # 탈퇴 후 다시 가입하면 선물 없음
    from tests.conftest import signup

    assert me.delete("/api/v1/me", json={"password": "goodpass123"}).status_code == 200
    again = signup(sent_codes, db, "me@hufs.ac.kr", gender="MALE")
    assert again.get("/api/v1/me/super-likes").json()["count"] == 0


def test_migration_0034_gives_recent_first_signups_one(tmp_path, monkeypatch):
    import uuid
    from datetime import datetime, timezone
    from pathlib import Path

    import sqlalchemy as sa
    from alembic import command
    from alembic.config import Config

    from app.core.config import get_settings
    from app.db.base import Base

    backend_dir = Path(__file__).resolve().parents[1]
    url = f"sqlite:///{tmp_path}/m.db"
    monkeypatch.setattr(get_settings(), "database_url", url)
    cfg = Config(str(backend_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir / "migrations"))
    command.upgrade(cfg, "0033_vip_renewal_discount")

    engine = sa.create_engine(url)
    users = Base.metadata.tables["users"]
    now = datetime.now(timezone.utc)

    def row(table=users, **given):
        r = dict(given)
        for col in table.columns:
            if col.name in r or col.nullable or col.server_default is not None:
                continue
            t = col.type
            r[col.name] = (
                False if isinstance(t, sa.Boolean) else 0 if isinstance(t, sa.Integer) else now if isinstance(t, sa.DateTime)
                else uuid.uuid4() if isinstance(t, sa.Uuid) else {} if isinstance(t, sa.JSON) else "x"
            )
        return r

    recent = datetime(2026, 11, 10, tzinfo=timezone.utc)
    old = datetime(2026, 11, 1, tzinfo=timezone.utc)
    people = {
        # 이름: (가입 시각, 상태, 메일 지문)
        "new": (recent, "ACTIVE", "h1"),
        "old": (old, "ACTIVE", "h2"),
        "gone": (recent, "DELETED", "h3"),
        "rejoin": (recent, "ACTIVE", "h4"),
        "rejoin_prev": (old, "DELETED", "h4"),
    }
    ids = {}
    uni = uuid.uuid4()
    with engine.begin() as conn:
        unis = Base.metadata.tables["universities"]
        conn.execute(unis.insert().values(row(unis, id=uni)))
        for name, (created, st, h) in people.items():
            ids[name] = uuid.uuid4()
            conn.execute(users.insert().values(row(
                id=ids[name], email=f"{name}@hufs.ac.kr", email_hash=h, status=st, created_at=created,
                deleted_at=now if st == "DELETED" else None, university_id=uni, super_likes=0,
                referral_code=None, referred_by_id=None,
            )))
    command.upgrade(cfg, "0034_signup_super_like_gift")
    with engine.connect() as conn:
        got = dict(conn.execute(sa.select(users.c.id, users.c.super_likes)).all())
    assert got[ids["new"]] == 1
    assert got[ids["old"]] == 0 and got[ids["gone"]] == 0 and got[ids["rejoin"]] == 0
    engine.dispose()
