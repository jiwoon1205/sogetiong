from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SECRET = "change-me-in-production"
# 문서·예시 파일에 공개된 값. 길이가 충분해도 운영에서 쓰면 안 된다.
PUBLIC_EXAMPLE_SECRETS = {DEFAULT_SECRET, "replace-with-a-long-random-secret"}


class Settings(BaseSettings):
    """앱 설정. 값은 backend/.env 파일이나 환경변수에서 읽는다."""

    app_name: str = "sogetiong"
    environment: Literal["dev", "prod", "test"] = Field(default="dev", alias="APP_ENV")
    database_url: str = "sqlite:///./sogetiong_dev.db"
    secret_key: str = DEFAULT_SECRET

    # --- 로그인(세션) ---
    session_cookie_name: str = "session"
    csrf_cookie_name: str = "csrf_token"
    admin_session_cookie_name: str = "admin_session"
    admin_csrf_cookie_name: str = "admin_csrf_token"
    session_days: int = 14
    admin_session_hours: int = 8
    # None이면 dev에서는 False, 그 외 환경에서는 True
    cookie_secure: bool | None = None

    # --- 가입 정책 ---
    min_age: int = 19  # 법률 검토 후 확정 (설계도 §44)
    max_age: int = 60
    password_min_length: int = 8
    verification_code_minutes: int = 10
    verification_ticket_minutes: int = 30
    rejoin_cooldown_days: int = 7  # 탈퇴 후 재가입까지 기다려야 하는 기간 (0이면 바로 가능)

    # --- 이메일 ---
    # smtp: 실제 발송 / console: 서버 콘솔에 코드 출력 (dev 전용)
    email_backend: Literal["smtp", "console"] = "smtp"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str = "no-reply@sogetiong.local"

    # --- 사진 ---
    storage_backend: Literal["local"] = "local"
    local_storage_dir: str = "./private_storage"
    photo_max_bytes: int = 5 * 1024 * 1024
    photo_max_side: int = 2048
    photo_resubmit_days: int = 30  # 승인된 평가 이후 재평가 요청 간격

    # --- 매칭 ---
    discover_page_size: int = 10
    require_approved_photo_to_discover: bool = True
    weight_interest: float = 0.40
    weight_appearance: float = 0.20  # 외적 평가는 "일부만" 반영 (설계도 §19)
    weight_preferred_department: float = 0.15
    weight_completeness: float = 0.15
    weight_mbti: float = 0.10
    weight_appearance_max: float = 0.30  # 외적 평가 가중치 상한

    cors_origins: str = "http://localhost:3000"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        populate_by_name=True,
        extra="ignore",
    )

    @property
    def cookies_secure(self) -> bool:
        if self.cookie_secure is not None:
            return self.cookie_secure
        return self.environment != "dev"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def validate_settings(self) -> None:
        if self.weight_appearance > self.weight_appearance_max:
            raise ValueError("WEIGHT_APPEARANCE가 상한(WEIGHT_APPEARANCE_MAX)을 넘습니다")
        if self.environment != "prod":
            return
        if self.secret_key in PUBLIC_EXAMPLE_SECRETS:
            raise ValueError(
                "SECRET_KEY가 예시 값 그대로입니다. 새로 만들어서 .env에 넣으세요: "
                'python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        if len(self.secret_key) < 32:
            raise ValueError("운영 환경에서는 32자 이상의 SECRET_KEY가 필요합니다")
        # 베타(사용자 500명 이하) 결정: DB는 SQLite, 사진은 서버 디스크에 저장하고 구글 드라이브로 매일 백업한다.
        # 다만 서버를 다시 만들면 사라지는 컨테이너 내부 경로가 아니라, 절대 경로(볼륨)여야 한다.
        if self.database_url.startswith("sqlite") and not self.database_url.startswith("sqlite:////"):
            raise ValueError("운영 환경의 SQLite 경로는 절대 경로여야 합니다 (예: sqlite:////data/sogetiong.db)")
        if self.storage_backend == "local" and not self.local_storage_dir.startswith("/"):
            raise ValueError("운영 환경의 LOCAL_STORAGE_DIR는 절대 경로여야 합니다 (예: /data/photos)")
        if self.email_backend != "smtp":
            raise ValueError("운영 환경에서는 EMAIL_BACKEND=smtp 이어야 합니다")
        if not self.cookies_secure:
            raise ValueError("운영 환경에서는 COOKIE_SECURE=true 이어야 합니다")
        if "null" in self.cors_origin_list or "*" in self.cors_origin_list:
            raise ValueError("운영 환경의 CORS_ORIGINS에는 실제 프론트엔드 주소만 넣어야 합니다")


@lru_cache
def get_settings() -> Settings:
    return Settings()
