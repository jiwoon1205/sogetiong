"""여성 회원 무료 · 성별 고정 (2026-11-07, `여성 무료·성별 고정 (2026-11-07)`).

- 여성 회원은 기본 이용권 없이 항상 기본 이용권 혜택 (상시, 설정 FEMALE_FREE). 기본 이용권은 살 수 없다
- 여성 회원의 VIP는 3,000원 (VIP_PRICE_FEMALE). 남성은 6,000원 그대로
- 그래도 들어온 기본 이용권 결제·쌓아 둔 일수는 같은 일수의 VIP로 바꿔 준다
- 마이그레이션 0030: 원하는 성별 → 이성, 여성의 남은 기본 기간 → VIP, 알림
(다른 테스트는 conftest에서 FEMALE_FREE=false로 돈다)
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from app.core.config import get_settings
from app.core.time import as_utc, utcnow
from app.services import membership_service
from tests.conftest import admin_login, ready_user, upload_photo
from tests.test_membership import paid_world, pay, switch_on, user_of  # noqa: F401  (paid_world는 fixture)


@pytest.fixture
def women_free(monkeypatch, paid_world):
    monkeypatch.setattr(paid_world, "female_free", True)
    switch_on(monkeypatch, paid_world, vip=True)
    return paid_world


def test_woman_has_basic_benefits_without_paying(sent_codes, db, women_free):
    admin = admin_login(db)
    her = ready_user(sent_codes, db, admin, "her@hufs.ac.kr", gender="FEMALE")
    him = ready_user(sent_codes, db, admin, "him@hufs.ac.kr", gender="MALE")

    m = her.get("/api/v1/me").json()["membership"]
    assert m["female_free"] is True and m["active"] is True and m["like_access"] == "paid"
    r = her.get("/api/v1/discover").json()
    assert r["like_access"] == "paid" and r["likes_left_today"] == women_free.daily_like_limit
    # 남성은 그대로 체험 이용자
    m = him.get("/api/v1/me").json()["membership"]
    assert m["female_free"] is False and m["like_access"] == "trial"

    # 좋아요 4개 이상도 된다 (체험 3개 제한 없음) — 받은 좋아요에 응답도 가능
    assert him.post("/api/v1/likes", json={"profile_id": her.profile_id}).status_code == 200
    r = her.post("/api/v1/likes", json={"profile_id": him.profile_id})
    assert r.status_code == 200 and r.json()["matched"] is True

    # 기본 이용권은 살 수 없다
    assert her.get("/api/v1/me/payment").json() == {"required": False}
    assert her.post("/api/v1/me/payment/request").status_code == 409


def test_woman_can_resubmit_photos_like_a_member(sent_codes, db, women_free, monkeypatch):
    admin = admin_login(db)
    her = ready_user(sent_codes, db, admin, "her@hufs.ac.kr", gender="FEMALE")
    him = ready_user(sent_codes, db, admin, "him@hufs.ac.kr", gender="MALE")
    # 재검토 대기 기간은 0으로 (이용권이 있느냐만 본다)
    monkeypatch.setattr(women_free, "photo_resubmit_days", 0)
    monkeypatch.setattr(women_free, "vip_photo_resubmit_days", 0)
    r = him.post("/api/v1/me/photos", files={"file": ("me.jpg", b"x", "image/jpeg")})
    assert r.status_code == 409 and r.json()["detail"] == "MEMBERSHIP_REQUIRED"
    upload_photo(her)  # 여성은 막히지 않는다


def test_vip_price_by_gender(sent_codes, db, women_free):
    admin = admin_login(db)
    her = ready_user(sent_codes, db, admin, "her@hufs.ac.kr", gender="FEMALE")
    him = ready_user(sent_codes, db, admin, "him@hufs.ac.kr", gender="MALE")
    vip = her.get("/api/v1/me/vip").json()
    assert vip["price"] == 3000 and vip["payment"]["amount"] == 3000 and vip["female_free"] is True
    assert vip["member_days_left"] is None
    assert him.get("/api/v1/me/vip").json()["price"] == 6000

    pay(admin, her, "vip")
    user = user_of(db, her)
    assert user.vip_until is not None and as_utc(user.vip_until) > utcnow() + timedelta(days=13)


def test_pending_basic_payment_becomes_vip(sent_codes, db, paid_world, monkeypatch):
    """여성 무료를 켜기 전에 "입금했어요"를 누른 기본 이용권 → 확인하면 같은 일수의 VIP."""
    switch_on(monkeypatch, paid_world, vip=True)
    admin = admin_login(db)
    her = ready_user(sent_codes, db, admin, "her@hufs.ac.kr", gender="FEMALE")
    assert her.post("/api/v1/me/payment/request").status_code == 200
    monkeypatch.setattr(paid_world, "female_free", True)
    pid = next(p for p in admin.get("/api/v1/admin/payments").json()["payments"] if p["kind"] == "SIGNUP")["payment_id"]
    assert admin.post(f"/api/v1/admin/payments/{pid}/confirm").status_code == 200
    user = user_of(db, her)
    assert user.vip_until is not None and as_utc(user.vip_until) > utcnow() + timedelta(days=13)


def test_banked_days_start_as_vip(sent_codes, db, women_free):
    admin = admin_login(db)
    her = ready_user(sent_codes, db, admin, "her@hufs.ac.kr", gender="FEMALE")
    user = user_of(db, her)
    user.member_days_banked = 14
    assert membership_service.start_banked(db, user) is True
    assert user.member_days_banked == 0
    assert as_utc(user.vip_until) > utcnow() + timedelta(days=13)


def test_switch_off_means_women_pay_again(sent_codes, db, women_free, monkeypatch):
    admin = admin_login(db)
    her = ready_user(sent_codes, db, admin, "her@hufs.ac.kr", gender="FEMALE")
    monkeypatch.setattr(women_free, "female_free", False)
    m = her.get("/api/v1/me").json()["membership"]
    assert m["female_free"] is False and m["like_access"] == "trial"
    assert her.get("/api/v1/me/vip").json()["price"] == 6000


# ---------- 마이그레이션 0030 ----------


def test_migration_0030(tmp_path, monkeypatch):
    from pathlib import Path

    backend_dir = Path(__file__).resolve().parents[1]
    url = f"sqlite:///{tmp_path}/m.db"
    monkeypatch.setattr(get_settings(), "database_url", url)
    cfg = Config(str(backend_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir / "migrations"))
    command.upgrade(cfg, "0029_relationship_goal")

    engine = sa.create_engine(url)
    # 표 정의는 앱 모델 것을 쓴다 (UUID 칸 변환 때문에. 0030은 칸을 바꾸지 않아서 0029 구조와 같다)
    from app.db.base import Base

    meta = Base.metadata
    users, pub, priv = meta.tables["users"], meta.tables["public_profiles"], meta.tables["private_profiles"]
    now = datetime.now(timezone.utc)

    def required(table, given):
        """NOT NULL인데 기본값이 없는 칸을 대충 채운다 (테스트용)."""
        row = dict(given)
        for col in table.columns:
            if col.name in row or col.nullable or col.server_default is not None:
                continue
            t = col.type
            if isinstance(t, sa.Boolean):
                row[col.name] = False
            elif isinstance(t, sa.Integer):
                row[col.name] = 0
            elif isinstance(t, sa.DateTime):
                row[col.name] = now
            elif isinstance(t, sa.Date):
                row[col.name] = now.date()
            elif isinstance(t, sa.Uuid):
                row[col.name] = uuid.uuid4()
            elif isinstance(t, sa.JSON):
                row[col.name] = {}
            else:
                row[col.name] = "x"
        return row

    people = {
        # 이름: (성별, 원하는 성별, member_until, vip_until)
        "woman_paid": ("FEMALE", "MALE", now + timedelta(days=10), None),
        "woman_vip": ("FEMALE", "MALE", now + timedelta(days=20), now + timedelta(days=5)),
        "woman_any": ("FEMALE", "ANY", None, None),
        "man_same": ("MALE", "MALE", now + timedelta(days=10), None),
    }
    ids = {}
    with engine.begin() as conn:
        uni = uuid.uuid4()
        conn.execute(meta.tables["universities"].insert().values(required(meta.tables["universities"], {"id": uni})))
        campus = uuid.uuid4()
        conn.execute(
            meta.tables["campuses"].insert().values(required(meta.tables["campuses"], {"id": campus, "university_id": uni}))
        )
        for name, (gender, want, member_until, vip_until) in people.items():
            uid = ids[name] = uuid.uuid4()
            conn.execute(
                users.insert().values(
                    required(
                        users,
                        {
                            "id": uid, "email": f"{name}@hufs.ac.kr", "status": "ACTIVE", "deleted_at": None,
                            "member_until": member_until, "vip_until": vip_until, "university_id": uni,
                            "referral_code": None, "referred_by_id": None,
                        },
                    )
                )
            )
            conn.execute(
                pub.insert().values(
                    required(pub, {"id": uuid.uuid4(), "user_id": uid, "gender": gender, "nickname": name, "campus_id": campus})
                )
            )
            conn.execute(priv.insert().values(required(priv, {"id": uuid.uuid4(), "user_id": uid, "preferred_gender": want})))

    command.upgrade(cfg, "head")

    with engine.connect() as conn:
        want = dict(conn.execute(sa.select(priv.c.user_id, priv.c.preferred_gender)).all())
        assert want[ids["woman_any"]] == "MALE" and want[ids["man_same"]] == "FEMALE"
        vip = dict(conn.execute(sa.select(users.c.id, users.c.vip_until)).all())
        assert as_utc(vip[ids["woman_paid"]]) > now + timedelta(days=9)  # 남은 10일 → VIP
        assert as_utc(vip[ids["woman_vip"]]) > now + timedelta(days=19)  # VIP 5일 + 그 뒤 기본 15일 → VIP 20일
        assert vip[ids["man_same"]] is None  # 남성은 그대로
        n = meta.tables["notifications"]
        titles = {}
        for uid, title in conn.execute(sa.select(n.c.user_id, n.c.title)).all():
            titles.setdefault(uid, set()).add(title)
        assert "추천 상대 기준이 바뀌었어요" in titles[ids["woman_any"]]
        assert "추천 상대 기준이 바뀌었어요" in titles[ids["man_same"]]
        assert "남은 이용권 기간을 VIP로 바꿔드렸어요" in titles[ids["woman_paid"]]
        assert "여성 회원은 기본 이용권이 무료예요" in titles[ids["woman_any"]]
        assert ids["man_same"] not in {u for u, t in titles.items() if "여성 회원은 기본 이용권이 무료예요" in t}
    engine.dispose()
