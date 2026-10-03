from datetime import date
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
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
    min_age: int = 18  # 2026-10-03: 만 18세부터 가입 가능하게 변경 (이전 19)
    max_age: int = 60
    # 매칭 조건의 나이 가로 바 오른쪽 끝. 여기까지 끌면 "35세 이상" = 나이 위쪽 제한 없음(max_age 비움)
    preference_age_cap: int = 35
    password_min_length: int = 8
    verification_code_minutes: int = 10
    verification_ticket_minutes: int = 30
    rejoin_cooldown_days: int = 7  # 탈퇴 후 재가입까지 기다려야 하는 기간 (0이면 바로 가능)
    # 탈퇴 후 프로필·사진 등을 관리자 확인용으로 보관하는 기간 (2026-10-01). 지나면 자동 삭제된다.
    withdrawn_retention_days: int = 7
    # 보관 기간이 지난 탈퇴자 정보를 지우는 작업을 몇 분마다 돌릴지 (0이면 끔, 테스트에서는 자동으로 끔)
    withdrawn_purge_interval_minutes: int = 60

    # --- 추천 ---
    # PASS한 사람이 다시 추천에 나오기까지 걸리는 시간 (2026-10-02). PASS를 누른 시각부터 센다.
    # 다시 나온 사람은 "처음 보는 사람" 뒤에 나온다. 다시 PASS하면 또 이 시간만큼 안 나온다.
    pass_cooldown_hours: int = 48

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
    photo_max_bytes: int = 10 * 1024 * 1024  # 한 장당. 화면에서 먼저 줄여서 보내므로 보통 1~2MB
    photo_max_count: int = 3  # 한 번에 제출할 수 있는 사진 수
    photo_max_side: int = 2048
    photo_resubmit_days: int = 7  # 평가 이후 새 사진(재검토)을 낼 수 있는 간격 (2026-10-01: 30일 → 7일)

    # --- 매칭 ---
    discover_page_size: int = 10
    require_approved_photo_to_discover: bool = True
    # 추천 순서 (2026-09-30 결정)
    # 1순위: 외모 등급(상/중/하)이 같은 사람 → 한 단계 차이 → 두 단계 차이
    # 2순위: 같은 등급 안에서는 아래 세부 점수로 정렬 (외모 숫자 점수는 등급과 겹치므로 쓰지 않음)
    weight_interest: float = 0.60
    weight_completeness: float = 0.25
    weight_mbti: float = 0.15
    # 활동 점수 (2026-10-01): 최근 ACTIVITY_WINDOW_DAYS일 중 접속한 날 수 ÷ 일수.
    # 매일 온 사람은 +0.20, 한 번도 안 온 사람은 +0. 외모 등급이 1순위인 것은 그대로다.
    weight_activity: float = 0.20
    activity_window_days: int = 14

    # 나를 LIKE한 사람 우대: 추천 한 페이지에 최대 이만큼 자리를 준다 (위치는 매번 랜덤)
    liked_me_slots: int = 2
    # 우대를 적용할 확률. 항상 넣으면 "이 카드 = 나를 좋아하는 사람"이라고 티가 난다.
    liked_me_probability: float = 0.7

    # 하루(한국 시간 자정 기준)에 보낼 수 있는 LIKE 수 (베타: 5개)
    daily_like_limit: int = 5

    # --- VIP (2026-10-03 정식 규칙) ---
    # 꺼져 있으면 VIP를 살 수 없고 "받은 LIKE" 탭도 안 보인다 (아래 테스트 계정은 예외).
    # 베타가 끝나는 날 SIGNUP_FEE_ENABLED와 함께 true로 바꾼다.
    vip_enabled: bool = False
    vip_days: int = 14  # 한 번 사면 2주 (2026-10-03, 30일에서 변경)
    vip_price: int = 6000
    # 오픈 할인: 이 날짜(한국 시간, 그날 포함)까지 vip_discount_price. 비우면 할인 없음.
    # 베타 종료일 + 2주로 정해서 .env에 넣는다 (예: VIP_DISCOUNT_UNTIL=2026-12-14)
    vip_discount_price: int = 4000
    vip_discount_until: date | None = None
    # VIP 혜택 숫자 (유료화 계획 1장)
    vip_daily_like_limit: int = 10  # 무료 5개 + 5개
    liker_boost_limit: int = 5  # "나를 LIKE한 사람" 우대는 보낸 사람의 하루 처음 5개 LIKE에만
    vip_pass_cooldown_hours: int = 24  # VIP가 PASS한 사람은 24시간 뒤 다시 (무료 48시간)
    vip_photo_resubmit_days: int = 3  # 사진 재검토 간격 (무료 7일)

    # VIP 테스트 계정 (2026-10-02). 여기 적힌 학교 메일 계정은 돈을 내지 않아도 항상 VIP다.
    # 2026-10-03부터 정식 VIP와 같은 규칙 (예전의 "LIKE 무제한", "PASS 즉시 다시 나옴"은 없어짐).
    # 여러 개는 쉼표로 구분. 끄려면 .env에 VIP_TEST_EMAILS= (빈 값)
    vip_test_emails: str = "wldns051205@hufs.ac.kr"

    # 매칭 조건은 하루(24시간)에 이 횟수만큼만 바꿀 수 있다 (처음 저장은 세지 않음)
    preferences_changes_per_day: int = 3

    # --- 가입비 (2026-10-03, 운영자 통장 직접 입금) ---
    # 꺼져 있으면 지금처럼 가입비 없이 사진을 낼 수 있고, 새 가입자도 베타 회원(면제)이 된다.
    # 베타가 끝나는 날 .env에 SIGNUP_FEE_ENABLED=true 를 넣고 다시 시작한다.
    signup_fee_enabled: bool = False
    signup_fee: int = 3000  # 남녀 같음
    # 입금받을 계좌. 코드·GitHub에 넣지 않고 서버 .env에만 적는다.
    payment_bank_name: str = ""
    payment_account_number: str = ""
    payment_account_holder: str = ""
    # 결제(입금 요청) 가능 시간, 한국 시간. 6~24 = 오전 6시부터 밤 12시 전까지.
    # 이 시간 밖에는 계좌번호를 숨기고 "입금했어요"를 받지 않는다 (확인·검수가 늦어지므로).
    payment_open_hour: int = 6
    payment_close_hour: int = 24

    # --- 문의 ---
    # 학과 변경 요청·"내 학과가 목록에 없어요" 문의를 받는 메일 주소 (화면에 표시됨)
    support_email: str = "support@private-matching.com"

    # --- 메일 속 링크·운영진 알림 ---
    # 메일 본문에 넣는 사이트 주소 (사진 검수 결과, 관리자 알림)
    site_url: str = "https://private-matching.com"
    # 검수 대기 사진이 이만큼 쌓이면 운영진에게 메일 한 통 (사진 한 장마다 보내면 메일이 너무 많다)
    photo_alert_threshold: int = 10

    cors_origins: str = "http://localhost:3000"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        populate_by_name=True,
        extra="ignore",
    )

    @field_validator("vip_discount_until", mode="before")
    @classmethod
    def _empty_date_is_none(cls, value):
        # .env에 VIP_DISCOUNT_UNTIL= (빈 값)으로 적어도 "할인 없음"으로 본다
        return None if isinstance(value, str) and not value.strip() else value

    @property
    def cookies_secure(self) -> bool:
        if self.cookie_secure is not None:
            return self.cookie_secure
        return self.environment != "dev"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def vip_test_email_set(self) -> set[str]:
        return {e.strip().lower() for e in self.vip_test_emails.split(",") if e.strip()}

    def validate_settings(self) -> None:
        if self.activity_window_days < 1:
            raise ValueError("ACTIVITY_WINDOW_DAYS는 1 이상이어야 합니다")
        if not 0 <= self.liked_me_probability <= 1:
            raise ValueError("LIKED_ME_PROBABILITY는 0~1 사이여야 합니다")
        if not 0 <= self.payment_open_hour < self.payment_close_hour <= 24:
            raise ValueError("PAYMENT_OPEN_HOUR < PAYMENT_CLOSE_HOUR (0~24) 이어야 합니다")
        if self.signup_fee_enabled and self.signup_fee <= 0:
            raise ValueError("SIGNUP_FEE는 0보다 커야 합니다")
        if self.vip_enabled and not (self.vip_price > 0 and self.vip_discount_price > 0 and self.vip_days > 0):
            raise ValueError("VIP_PRICE, VIP_DISCOUNT_PRICE, VIP_DAYS는 0보다 커야 합니다")
        if (self.signup_fee_enabled or self.vip_enabled) and not (
            self.payment_bank_name and self.payment_account_number and self.payment_account_holder
        ):
            raise ValueError(
                "SIGNUP_FEE_ENABLED 또는 VIP_ENABLED가 true 이면 PAYMENT_BANK_NAME, PAYMENT_ACCOUNT_NUMBER, "
                "PAYMENT_ACCOUNT_HOLDER를 .env에 넣어야 합니다"
            )
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
