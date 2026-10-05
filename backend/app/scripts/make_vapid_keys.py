"""휴대폰 알림용 VAPID 열쇠 한 쌍을 만들어 화면에 출력한다 (2026-10-05).

서버에서 한 번만 실행하고, 출력된 두 줄을 deploy/backend.env 에 붙여 넣는다:
    docker compose exec backend python -m app.scripts.make_vapid_keys

⚠️ VAPID_PRIVATE_KEY는 비밀번호 관리자에 보관하고 GitHub에 올리지 않는다.
⚠️ 한 번 쓰기 시작하면 바꾸지 않는다 (바꾸면 모든 사람이 알림을 다시 켜야 한다).
"""

import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def make_keys() -> tuple[str, str]:
    """(공개 열쇠, 비밀 열쇠) — 둘 다 base64url 글자."""
    private = ec.generate_private_key(ec.SECP256R1())
    private_raw = private.private_numbers().private_value.to_bytes(32, "big")
    public_raw = private.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    return _b64url(public_raw), _b64url(private_raw)


def main() -> None:
    public, private = make_keys()
    print("# 아래 두 줄을 deploy/backend.env 에 붙여 넣으세요 (비밀 열쇠는 비밀번호 관리자에도 보관)")
    print(f"VAPID_PUBLIC_KEY={public}")
    print(f"VAPID_PRIVATE_KEY={private}")


if __name__ == "__main__":
    main()
