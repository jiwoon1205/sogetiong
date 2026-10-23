from datetime import datetime, timezone
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.time import KST

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
    # 탈퇴 후 재가입까지 기다려야 하는 기간 (0이면 바로 가능).
    # 2026-10-05: 7 → 0. 재가입하면 사진·점수·재검토 대기·이용권을 이어받으므로(auth_service.carry_over_account) 바로 허용
    rejoin_cooldown_days: int = 0
    # 탈퇴 후 프로필·사진 등을 관리자 확인용으로 보관하는 기간 (2026-10-01). 지나면 자동 삭제된다.
    withdrawn_retention_days: int = 7
    # 보관 기간이 지난 탈퇴자 정보를 지우는 작업을 몇 분마다 돌릴지 (0이면 끔, 테스트에서는 자동으로 끔)
    withdrawn_purge_interval_minutes: int = 60

    # --- 추천 ---
    # PASS한 사람이 다시 추천에 나오기까지 걸리는 시간 (2026-10-02). PASS를 누른 시각부터 센다.
    # 다시 나온 사람은 "처음 보는 사람" 뒤에 나온다. 다시 PASS하면 또 이 시간만큼 안 나온다.
    pass_cooldown_hours: int = 48

    # 하루 매칭 한도 (2026-10-06). 한국 시간 0시부터 매칭이 N번 생기면, 그날은 추천 탭에
    # "나를 이미 LIKE한 사람"이 안 나온다. 밤 12시에 자동으로 풀린다. 본인은 모른다. 0이면 끔.
    # 2026-10-24 추천 재설계: 없앰 (사용자 결정). 추천에서는 더 이상 쓰지 않는다.
    daily_match_limit: int = 0

    # --- 이메일 ---
    # smtp: 실제 발송 / console: 서버 콘솔에 코드 출력 (dev 전용)
    email_backend: Literal["smtp", "console"] = "smtp"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str = "no-reply@sogetiong.local"

    # --- 사진 ---
    local_storage_dir: str = "./private_storage"
    photo_max_bytes: int = 10 * 1024 * 1024  # 한 장당. 화면에서 먼저 줄여서 보내므로 보통 1~2MB
    photo_max_count: int = 3  # 한 번에 제출할 수 있는 사진 수
    photo_max_side: int = 2048
    photo_resubmit_days: int = 7  # 평가 이후 새 사진(재검토)을 낼 수 있는 간격 (2026-10-01: 30일 → 7일)

    # --- 매칭 ---
    discover_page_size: int = 10
    require_approved_photo_to_discover: bool = True
    # 추천 = 가중치 추첨 (2026-10-24 재설계, 프로젝트 문서 "추천 알고리즘 재설계 (2026-10-24)")
    # 조건이 맞는 모든 사람이 추첨 대상. 가중치 = ①등급 × ②활동 × ③나를 좋아요한 횟수 × ④취향, 네 요소 모두 최대 2배.
    rec_tier_same: float = 2.0  # ① 외모 등급이 같음
    rec_tier_one: float = 1.4  # ① 한 단계 차이
    rec_tier_two: float = 1.0  # ① 두 단계 차이
    rec_activity_max: float = 2.0  # ② 최근 14일 매일 접속한 사람의 배수 (한 번도 안 오면 1)
    rec_liked_max: float = 2.0  # ③ 나에게 좋아요를 REC_LIKED_FULL번 보낸 사람의 배수
    rec_liked_full: int = 4  # ③ 이 횟수에서 최대 (5번째 좋아요는 바로 매칭)
    rec_taste_max: float = 2.0  # ④ 관심사(겹치는 수)·MBTI가 가장 잘 맞을 때의 배수
    rec_effort_max: float = 2.0  # ⑤ 프로필을 정성껏 다 채웠을 때의 배수 (matching_service.effort)
    # 좋아요 쌓기 (2026-10-24): 매칭이 안 되면 마지막 좋아요 후 이 시간이 지나 다시 추천에 나온다.
    # 같은 사람에게 이 횟수째 좋아요를 보내면 바로 매칭 (슈퍼 라이크와 같은 효과)
    like_repeat_hours: int = 48
    like_repeat_match_count: int = 5
    # ④ 취향 점수 안의 비중. 2026-10-24: 관심사 0.60→0.80, 완성도 0.25→0 (⑤ 프로필 정성으로 옮김), MBTI 0.15→0.20
    weight_interest: float = 0.80
    weight_completeness: float = 0.0
    weight_mbti: float = 0.20
    # 활동 점수 (2026-10-01): 최근 ACTIVITY_WINDOW_DAYS일 중 접속한 날 수 ÷ 일수.
    # 2026-10-24: 0.20 → 0 (사용자 결정). 오래 안 들어온 사람(유령회원)이 같은 등급 안에서 늘 맨 뒤로 밀려
    # 사실상 추천에 안 나왔다 → 접속 빈도와 상관없이 활성 회원과 같은 조건으로 나오게 한다.
    # 다시 켜려면 .env에 WEIGHT_ACTIVITY=0.2
    weight_activity: float = 0.0
    activity_window_days: int = 14

    # (2026-10-24 재설계로 안 씀) 예전 "나를 LIKE한 사람 한 페이지 최대 2자리" → 가중치 ③으로 바뀜
    liked_me_slots: int = 2
    # 슈퍼 VIP (2026-10-12): 추천 한 페이지 맨 앞에 넣는 최대 인원. 여러 명이면 그중 랜덤
    super_vip_slots: int = 2
    # 슈퍼 라이크 (2026-10-12): 1개 가격, 한 번에 살 수 있는 최대 개수. 판매는 MEMBERSHIP_ENABLED를 따른다
    super_like_price: int = 1000
    super_like_max_quantity: int = 10
    # 우대를 적용할 확률. 항상 넣으면 "이 카드 = 나를 좋아하는 사람"이라고 티가 난다.
    liked_me_probability: float = 0.7

    # 하루(한국 시간 자정 기준)에 보낼 수 있는 LIKE 수 (베타: 5개)
    daily_like_limit: int = 5

    # --- VIP (2026-10-03 정식 규칙) ---
    # 꺼져 있으면 VIP를 살 수 없다 (아래 테스트 계정은 예외).
    # 베타가 끝나는 날 MEMBERSHIP_ENABLED와 함께 true로 바꾼다 (VIP는 기본 이용권을 포함하므로 둘은 같이 켠다).
    vip_enabled: bool = False
    # 미리 보기 (2026-10-04): VIP 판매 전에도 모든 사람에게 "받은 LIKE" 탭을 보여준다.
    # 누르면 VIP 혜택 안내 + 아래 문구가 나오고, 결제 버튼은 없다 (VIP_ENABLED가 켜져야 살 수 있음).
    # 탭을 다시 숨기려면 .env에 VIP_PREVIEW=false
    vip_preview: bool = True
    vip_preview_notice: str = "VIP는 무료 베타가 끝나는 날(10월 8일)부터 살 수 있어요."
    vip_days: int = 14  # 한 번 사면 2주, 기본 이용권 포함 (2026-10-06: 4주 → 2주, 가격 그대로). 베타 기간 구매는 BETA_PERIOD_DAYS
    vip_price: int = 6000  # 할인 없음 (2026-10-04, 오픈 할인 4,000원 취소)
    # VIP 혜택 숫자 (유료화 계획 1장)
    vip_daily_like_limit: int = 10  # 무료 5개 + 5개
    liker_boost_limit: int = 5  # "나를 LIKE한 사람" 우대는 보낸 사람의 하루 처음 5개 LIKE에만
    vip_pass_cooldown_hours: int = 24  # VIP가 PASS한 사람은 24시간 뒤 다시 (무료 48시간)
    vip_photo_resubmit_days: int = 3  # 사진 재검토 간격 (무료 7일)

    # VIP 테스트 계정 (2026-10-02). 여기 적힌 학교 메일 계정은 돈을 내지 않아도 항상 VIP다.
    # 2026-10-03부터 정식 VIP와 같은 규칙 (예전의 "LIKE 무제한", "PASS 즉시 다시 나옴"은 없어짐).
    # 여러 개는 쉼표로 구분. 끄려면 .env에 VIP_TEST_EMAILS= (빈 값)
    vip_test_emails: str = "wldns051205@hufs.ac.kr"

    # --- 학교 확장 (2026-10-24, 경희대) ---
    # 한국외대는 항상 열려 있다. 다른 학교는 여기에 메일 주소 뒷부분을 적어야 열린다 (오픈 스위치).
    # 예: OPEN_SCHOOLS=khu.ac.kr  (여러 개는 쉼표). 바꾼 뒤 backend를 다시 시작하면 적용된다 (seed가 켜고 끔).
    # 열리지 않은 학교는 가입할 수 없고, 그 학교 사람은 다른 학생 추천에 나오지 않는다.
    open_schools: str = ""
    # 열기 전 테스트용 계정 (2026-10-24). "학교메일뒷부분:가입할메일" 형식, 여러 개는 쉼표.
    # 예: SCHOOL_TEST_EMAILS=khu.ac.kr:my.personal@gmail.com → 이 메일로 가입하면 경희대 학생으로 가입된다 (학교가 닫혀 있어도).
    # 닫힌 학교 사람은 같은 학교 사람과 VIP 테스트 계정(VIP_TEST_EMAILS)하고만 서로 추천에 나온다.
    # 테스트가 끝나면 빈 값으로 되돌리고 테스트 계정은 탈퇴한다.
    school_test_emails: str = ""

    # --- 친구 초대 이벤트 (2026-10-24) ---
    # 이 기간(한국 시간)에 초대 링크로 가입한 사람의 첫 사진이 승인되면, 초대한 사람에게 슈퍼 라이크 1개.
    # 기본: 2026-10-24 0시 ~ 2026-11-07 0시 (2주, 11월 6일 밤 12시에 끝). 끄려면 REFERRAL_END를 지난 시각으로.
    referral_start: datetime | None = datetime(2026, 10, 24, 0, 0, tzinfo=KST)
    referral_end: datetime | None = datetime(2026, 11, 7, 0, 0, tzinfo=KST)
    # 한 사람이 초대로 받을 수 있는 슈퍼 라이크 최대 개수. 0 = 한도 없음 (2026-10-24 결정)
    referral_max_rewards: int = 0
    # 탈퇴 후 이 일수 안에 다시 가입한 계정은 초대로 치지 않는다 (2026-10-24: "재가입 전부 제외" → "7일 안 재가입만 제외")
    referral_rejoin_exclude_days: int = 7

    # 매칭 조건은 하루(24시간)에 이 횟수만큼만 바꿀 수 있다 (처음 저장은 세지 않음)
    preferences_changes_per_day: int = 3

    # --- 이용권 (2026-10-04 구독제, 운영자 통장 직접 입금) ---
    # 꺼져 있으면 지금처럼 모두 무료로 쓴다 (결제 단계 없음, 추천 제한 없음).
    # 켜면 모든 회원(베타 회원 포함)이 기본 이용권(2주) 또는 VIP(2주, 기본 포함)가 있어야 추천을 본다.
    # 이용권이 없어도 이미 매칭된 사람과 대화는 된다.
    # 베타가 끝나는 날 .env에 MEMBERSHIP_ENABLED=true, VIP_ENABLED=true 를 넣고 다시 시작한다.
    # (예전 이름 SIGNUP_FEE_ENABLED는 더 이상 읽지 않는다)
    membership_enabled: bool = False
    # 기본 이용권 가격 (2026-10-06): 정가 4,000원, MEMBERSHIP_DISCOUNT_UNTIL 전까지는 할인가 3,000원. 남녀 같음
    membership_price: int = 4000
    membership_discount_price: int = 3000
    # 할인이 끝나는 시각. 비워 두면 할인 없음. 예: MEMBERSHIP_DISCOUNT_UNTIL=2026-10-08T00:00:00+09:00
    membership_discount_until: datetime | None = None
    # 기본 이용권 기간 (2026-10-06: 4주 → 2주, 가격 그대로)
    membership_days: int = 14
    # 베타 기간(OPEN_AT 전)에 "입금했어요"를 누른 이용권·VIP는 이 일수 (2026-10-06: 베타 구매는 4주 유지)
    beta_period_days: int = 28
    # 남은 기간이 이 일수 이하면 추천 화면 위에 "○일 남았어요" 띠를 보여준다 (알림은 보내지 않음)
    membership_warn_days: int = 3
    # 입금받을 계좌. 코드·GitHub에 넣지 않고 서버 .env에만 적는다.
    payment_bank_name: str = ""
    payment_account_number: str = ""
    payment_account_holder: str = ""
    # 결제(입금 요청) 가능 시간, 한국 시간. 6~24 = 오전 6시부터 밤 12시 전까지.
    # 이 시간 밖에는 계좌번호를 숨기고 "입금했어요"를 받지 않는다 (확인·검수가 늦어지므로).
    payment_open_hour: int = 6
    payment_close_hour: int = 24

    # --- 유료 시작 시각 (2026-10-06, 점검 기간 없앰) ---
    # MEMBERSHIP_ENABLED=true여도 이 시각 전에는 베타처럼 모두 무료로 쓴다 (하루 LIKE 5개).
    # 이 시각이 되면 서버를 다시 켜지 않아도 자동으로 유료가 시작된다:
    #   이용권이 없는 사람(베타 회원 포함)은 모두 체험 이용자(LIKE 평생 FREE_TRIAL_LIKES개)가 된다.
    # 이 시각 전에 미리 산(입금했어요를 누른) 이용권은 이 시각부터 4주(BETA_PERIOD_DAYS)를 센다. 그 뒤에 사면 2주. 비워 두면 스위치를 켠 순간부터 유료.
    # 예: OPEN_AT=2026-10-08T00:00:00+09:00  (시간대를 빼고 쓰면 한국 시간으로 본다)
    open_at: datetime | None = None

    # --- 무료 체험 (2026-10-06, `무료 체험 플랜 설계`) ---
    # 이용권이 없는 사람이 보낼 수 있는 LIKE 수 (평생, 다시 안 생김). 다 쓰면 추천·PASS·대화는 되고 LIKE만 막힌다.
    # 이용권을 사면 체험은 끝난다. 탈퇴·재가입해도 이어진다. 0이면 체험 없음.
    free_trial_likes: int = 3

    # --- 문의 ---
    # 학과 변경 요청·"내 학과가 목록에 없어요" 문의를 받는 메일 주소 (화면에 표시됨)
    support_email: str = "support@private-matching.com"

    # --- 메일 속 링크·운영진 알림 ---
    # 메일 본문에 넣는 사이트 주소 (사진 검수 결과, 관리자 알림)
    site_url: str = "https://private-matching.com"
    # 검수 대기 사진이 이만큼 쌓이면 운영진에게 메일 한 통 (사진 한 장마다 보내면 메일이 너무 많다)
    photo_alert_threshold: int = 10

    # --- 휴대폰 알림 (웹 푸시, 2026-10-05) ---
    # VAPID 열쇠: 우리 서버가 보낸 알림이라는 걸 증명하는 열쇠 한 쌍. 서버에서 한 번 만들어 .env에 넣는다:
    #   docker compose exec backend python -m app.scripts.make_vapid_keys
    # 비어 있으면 휴대폰 알림은 꺼진 상태다 (설정 화면에 "준비 중"으로 보이고, 메일 알림만 간다).
    # ⚠️ 한 번 쓰기 시작하면 바꾸지 않는다 (바꾸면 모든 사람이 알림을 다시 켜야 한다).
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:support@private-matching.com"
    # 휴대폰 알림은 메시지마다 보낸다 (카톡·DM처럼, 2026-10-05 변경).
    # 휴대폰 알림을 못 받아 메일로 대신 보낼 때만, 같은 대화방(같은 종류)은 이 시간에 한 번 (메일함이 넘치지 않게)
    email_alert_throttle_minutes: int = 10
    # 이 시간(초) 안에 그 대화방 화면이 새 메시지를 확인했으면 "보는 중"이라 새 메시지 알림을 생략한다.
    # 대화방 화면은 4초마다 확인한다 → 12초면 확인 2번을 놓쳐도 "보는 중"으로 본다 (2026-10-06: 45초·사이트 전체 → 12초·그 대화방만)
    push_skip_if_viewing_seconds: int = 12
    # 한 사람이 알림을 켤 수 있는 기기 수. 넘으면 가장 오래된 기기부터 지운다.
    push_max_devices: int = 5

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

    @field_validator("open_at", "membership_discount_until", mode="before")
    @classmethod
    def _blank_datetime(cls, v):
        # .env에 OPEN_AT= (빈 값)으로 남아 있어도 서버가 안 켜지는 일이 없게 "없음"으로 본다
        return None if isinstance(v, str) and not v.strip() else v

    @staticmethod
    def _to_utc(value: datetime | None) -> datetime | None:
        """시간대 없이 적었으면 한국 시간으로 본다."""
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=KST).astimezone(timezone.utc)
        return value.astimezone(timezone.utc)

    @property
    def open_at_utc(self) -> datetime | None:
        """유료 시작 시각(UTC)."""
        return self._to_utc(self.open_at)

    @property
    def membership_discount_until_utc(self) -> datetime | None:
        return self._to_utc(self.membership_discount_until)

    @property
    def referral_start_utc(self) -> datetime | None:
        return self._to_utc(self.referral_start)

    @property
    def referral_end_utc(self) -> datetime | None:
        return self._to_utc(self.referral_end)

    @property
    def push_enabled(self) -> bool:
        return bool(self.vapid_public_key.strip() and self.vapid_private_key.strip())

    @property
    def vip_test_email_set(self) -> set[str]:
        return {e.strip().lower() for e in self.vip_test_emails.split(",") if e.strip()}

    @property
    def open_school_domains(self) -> set[str]:
        return {d.strip().lower().lstrip("@") for d in self.open_schools.split(",") if d.strip()}

    @property
    def school_test_email_map(self) -> dict[str, str]:
        """{가입할 메일: 학교 메일 뒷부분}. 형식이 틀린 항목은 무시한다."""
        result = {}
        for item in self.school_test_emails.split(","):
            domain, sep, email = item.partition(":")
            if sep and domain.strip() and "@" in email:
                result[email.strip().lower()] = domain.strip().lower().lstrip("@")
        return result

    def validate_settings(self) -> None:
        if self.activity_window_days < 1:
            raise ValueError("ACTIVITY_WINDOW_DAYS는 1 이상이어야 합니다")
        if not 0 <= self.liked_me_probability <= 1:
            raise ValueError("LIKED_ME_PROBABILITY는 0~1 사이여야 합니다")
        if not 0 <= self.payment_open_hour < self.payment_close_hour <= 24:
            raise ValueError("PAYMENT_OPEN_HOUR < PAYMENT_CLOSE_HOUR (0~24) 이어야 합니다")
        if self.membership_enabled and not (self.membership_price > 0 and self.membership_days > 0):
            raise ValueError("MEMBERSHIP_PRICE, MEMBERSHIP_DAYS는 0보다 커야 합니다")
        if self.beta_period_days <= 0:
            raise ValueError("BETA_PERIOD_DAYS는 0보다 커야 합니다")
        if self.membership_discount_until is not None and not 0 < self.membership_discount_price <= self.membership_price:
            raise ValueError("MEMBERSHIP_DISCOUNT_PRICE는 0보다 크고 MEMBERSHIP_PRICE 이하여야 합니다")
        if self.free_trial_likes < 0:
            raise ValueError("FREE_TRIAL_LIKES는 0 이상이어야 합니다")
        if self.vip_enabled and not (self.vip_price > 0 and self.vip_days > 0):
            raise ValueError("VIP_PRICE, VIP_DAYS는 0보다 커야 합니다")
        if self.vip_enabled and not self.membership_enabled:
            raise ValueError("VIP_ENABLED를 켜려면 MEMBERSHIP_ENABLED도 켜야 합니다 (VIP는 기본 이용권을 포함)")
        if (self.membership_enabled or self.vip_enabled) and not (
            self.payment_bank_name and self.payment_account_number and self.payment_account_holder
        ):
            raise ValueError(
                "MEMBERSHIP_ENABLED 또는 VIP_ENABLED가 true 이면 PAYMENT_BANK_NAME, PAYMENT_ACCOUNT_NUMBER, "
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
        if not self.local_storage_dir.startswith("/"):
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
