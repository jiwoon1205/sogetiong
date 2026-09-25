"""관리자 계정 만들기 (2단계 인증 포함).

실행: python -m app.scripts.create_admin --email admin@example.com --role SUPER_ADMIN
비밀번호는 화면에 표시되지 않게 입력받는다.
출력되는 otpauth:// 주소를 QR 코드로 만들거나, 비밀키를 Google Authenticator 등에 직접 입력한다.
"""

import argparse
import getpass

import pyotp

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.admin import ROLE_PERMISSIONS, AdminRole, AdminUser


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--role", required=True, choices=sorted(ROLE_PERMISSIONS))
    args = parser.parse_args()

    password = getpass.getpass("비밀번호 (12자 이상): ")
    if len(password) < 12:
        raise SystemExit("관리자 비밀번호는 12자 이상이어야 합니다.")
    if password != getpass.getpass("비밀번호 확인: "):
        raise SystemExit("비밀번호가 일치하지 않습니다.")

    db = SessionLocal()
    try:
        role = db.query(AdminRole).filter(AdminRole.name == args.role).first()
        if role is None:
            raise SystemExit("역할이 없습니다. 먼저 python -m app.scripts.seed 를 실행하세요.")
        email = args.email.strip().lower()
        if db.query(AdminUser.id).filter(AdminUser.email == email).first():
            raise SystemExit("이미 있는 관리자 이메일입니다.")
        secret = pyotp.random_base32()
        db.add(AdminUser(email=email, password_hash=hash_password(password), role_id=role.id, totp_secret=secret))
        db.commit()
    finally:
        db.close()

    uri = pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=get_settings().app_name)
    print("관리자 계정을 만들었습니다.")
    print(f"2단계 인증 비밀키: {secret}")
    print(f"인증 앱 등록 주소: {uri}")
    print("⚠️ 이 비밀키는 다시 표시되지 않습니다. 인증 앱에 바로 등록하세요.")


if __name__ == "__main__":
    main()
