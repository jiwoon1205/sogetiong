"""테스트 공통 준비물.

- 테스트마다 빈 SQLite DB를 새로 만든다.
- 인증 메일은 실제로 보내지 않고 sent_codes에 모아둔다.
- UserClient는 사용자 한 명의 브라우저라고 생각하면 된다 (쿠키 + CSRF 헤더 자동 처리).
"""

import os
import sys
import tempfile
from datetime import date
from io import BytesIO
from pathlib import Path

_tmp = tempfile.mkdtemp(prefix="sogetiong-test-")
os.environ.update(
    {
        "APP_ENV": "test",
        "DATABASE_URL": os.environ.get("TEST_DATABASE_URL", f"sqlite:///{_tmp}/test.db"),
        "LOCAL_STORAGE_DIR": f"{_tmp}/storage",
        "EMAIL_BACKEND": "console",
        "SECRET_KEY": "test-secret-key-that-is-long-enough-123456",
    }
)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pyotp  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from app.core.rate_limit import reset_rate_limits  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import AdminRole, AdminUser, Campus, Department  # noqa: E402
from app.scripts import seed  # noqa: E402

BASE_URL = "https://testserver"  # Secure 쿠키가 전송되도록 https


@pytest.fixture(autouse=True)
def fresh_db(monkeypatch):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    reset_rate_limits()
    seed.run()
    yield


@pytest.fixture
def sent_codes(monkeypatch):
    codes: dict[str, str] = {}
    monkeypatch.setattr(
        "app.services.email_service.EmailService.send_verification_code",
        staticmethod(lambda email, code: codes.__setitem__(email, code)),
    )
    return codes


@pytest.fixture
def reset_mail(monkeypatch):
    """비밀번호 재설정 메일을 실제로 보내지 않고 모아둔다.

    reset_mail["codes"][email] = 마지막으로 보낸 재설정 코드
    reset_mail["notices"] = 비밀번호 변경 안내 메일을 받은 주소 목록
    """
    box: dict = {"codes": {}, "notices": []}
    monkeypatch.setattr(
        "app.services.email_service.EmailService.send_password_reset_code",
        staticmethod(lambda email, code: box["codes"].__setitem__(email, code)),
    )
    monkeypatch.setattr(
        "app.services.email_service.EmailService.send_password_changed_notice",
        staticmethod(lambda email: box["notices"].append(email)),
    )
    return box


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


class UserClient:
    """브라우저 한 개. 데이터를 바꾸는 요청에는 CSRF 헤더를 자동으로 붙인다."""

    csrf_cookie = "csrf_token"

    def __init__(self):
        self.http = TestClient(app, base_url=BASE_URL)
        self.profile_id: str | None = None

    def _headers(self, kwargs):
        headers = dict(kwargs.pop("headers", {}) or {})
        token = self.http.cookies.get(self.csrf_cookie)
        if token and kwargs.pop("csrf", True):
            headers["X-CSRF-Token"] = token
        return headers

    def get(self, url, **kw):
        return self.http.get(url, **kw)

    def post(self, url, **kw):
        return self.http.post(url, headers=self._headers(kw), **kw)

    def put(self, url, **kw):
        return self.http.put(url, headers=self._headers(kw), **kw)

    def patch(self, url, **kw):
        return self.http.patch(url, headers=self._headers(kw), **kw)

    def delete(self, url, **kw):
        return self.http.request("DELETE", url, headers=self._headers(kw), **kw)


class AdminClient(UserClient):
    csrf_cookie = "admin_csrf_token"


def campus_id(db, name="서울캠퍼스") -> str:
    return str(db.query(Campus).filter(Campus.name == name).one().id)


def department_id(db, name) -> str:
    return str(db.query(Department).filter(Department.name == name).one().id)


def jpeg_with_exif() -> bytes:
    """휴대폰 사진처럼 EXIF(촬영기기·GPS)가 들어있는 JPEG."""
    image = Image.new("RGB", (64, 48), (200, 120, 90))
    exif = Image.Exif()
    exif[0x010F] = "PhoneMaker"  # Make
    exif[0x8825] = {1: "N", 2: (37.0, 35.0, 50.0)}  # GPS
    out = BytesIO()
    image.save(out, format="JPEG", exif=exif)
    return out.getvalue()


def signup(sent_codes, db, email, *, gender="FEMALE", birth=date(2003, 5, 1), campus="서울캠퍼스", nickname=None) -> UserClient:
    client = UserClient()
    r = client.post("/api/v1/auth/email/send-code", json={"email": email})
    assert r.status_code == 202, r.text
    r = client.post("/api/v1/auth/email/verify", json={"email": email, "code": sent_codes[email]})
    assert r.status_code == 200, r.text
    r = client.post(
        "/api/v1/auth/register",
        json={
            "verification_ticket": r.json()["verification_ticket"],
            "password": "goodpass123",
            "nickname": nickname or ("user_" + email.split("@")[0]),
            "gender": gender,
            "birth_date": birth.isoformat(),
            "campus_id": campus_id(db, campus),
            "agree_terms": True,
            "agree_privacy": True,
            "agree_appearance_public": True,
        },
    )
    assert r.status_code == 201, r.text
    client.profile_id = client.get("/api/v1/me/profile").json()["profile_id"]
    return client


def set_preferences(client: UserClient, **overrides):
    body = {"preferred_gender": "ANY", "min_age": 19, "max_age": 30, "campus_mode": "ALL"}
    body.update(overrides)
    r = client.put("/api/v1/me/preferences", json=body)
    assert r.status_code == 200, r.text
    return r


def make_admin(db, email="admin@test.com", role="SUPER_ADMIN") -> tuple[str, str]:
    """(email, totp_secret)"""
    secret = pyotp.random_base32()
    role_row = db.query(AdminRole).filter(AdminRole.name == role).one()
    db.add(AdminUser(email=email, password_hash=hash_password("admin-password-1234"), role_id=role_row.id, totp_secret=secret))
    db.commit()
    return email, secret


def admin_login(db, role="SUPER_ADMIN", email=None) -> AdminClient:
    email, secret = make_admin(db, email or f"{role.lower()}@test.com", role)
    client = AdminClient()
    r = client.post("/api/v1/admin/auth/login", json={"email": email, "password": "admin-password-1234"})
    assert r.status_code == 200, r.text
    r = client.post("/api/v1/admin/auth/2fa", json={"code": pyotp.TOTP(secret).now()})
    assert r.status_code == 200, r.text
    return client


def upload_photo(client: UserClient) -> str:
    r = client.post("/api/v1/me/photos", files={"file": ("me.jpg", jpeg_with_exif(), "image/jpeg")})
    assert r.status_code == 201, r.text
    return r.json()["photo_id"]


def approve(admin: AdminClient, photo_id: str, scores=(7, 7, 7, 7)):
    r = admin.put(
        f"/api/v1/admin/photo-reviews/{photo_id}/evaluation",
        json={
            "decision": "APPROVED",
            "overall_impression": scores[0],
            "style": scores[1],
            "grooming": scores[2],
            "photo_vibe": scores[3],
        },
    )
    assert r.status_code == 200, r.text
    return r


DEFAULT_DEPARTMENT = {"서울캠퍼스": "경영학부", "글로벌캠퍼스": "컴퓨터공학부"}


def choose_department(client: UserClient, db, name: str, *, show_campus=True, show_department=True):
    """프로필 작성 단계: 학과 + 캠퍼스·학과 공개 여부를 고른다."""
    r = client.patch(
        "/api/v1/me/profile",
        json={"department_id": department_id(db, name), "show_campus": show_campus, "show_department": show_department},
    )
    assert r.status_code == 200, r.text
    return r


def ready_user(sent_codes, db, admin, email, **kw) -> UserClient:
    """가입 + 학과 + 매칭 조건 + 사진 승인까지 끝난 사용자."""
    prefs = kw.pop("prefs", {})
    dept = kw.pop("dept", None) or DEFAULT_DEPARTMENT[kw.get("campus", "서울캠퍼스")]
    show_campus = kw.pop("show_campus", True)
    show_department = kw.pop("show_department", True)
    client = signup(sent_codes, db, email, **kw)
    choose_department(client, db, dept, show_campus=show_campus, show_department=show_department)
    set_preferences(client, **prefs)
    approve(admin, upload_photo(client))
    return client


def discover_ids(client: UserClient) -> list[str]:
    r = client.get("/api/v1/discover")
    assert r.status_code == 200, r.text
    return [card["profile_id"] for card in r.json()["profiles"]]
