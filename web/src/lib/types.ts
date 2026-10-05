export type Scores = {
  overall_impression: number;
  style: number;
  grooming: number;
  photo_vibe: number;
};

export const SCORE_LABELS: { key: keyof Scores; label: string; hint: string }[] = [
  { key: "overall_impression", label: "전체적인 인상", hint: "첫눈에 주는 전반적인 인상" },
  { key: "style", label: "스타일", hint: "옷차림·헤어 등 스타일의 조화" },
  { key: "grooming", label: "자기관리", hint: "청결함, 단정함, 관리된 느낌" },
  { key: "photo_vibe", label: "사진 분위기", hint: "사진이 전달하는 분위기와 표정" },
];

export type Card = {
  profile_id: string;
  nickname: string;
  age: number | null;
  gender: "MALE" | "FEMALE";
  campus: string | null;
  department: string | null;
  mbti: string | null;
  bio: string | null;
  ideal_type: string | null;
  /** 본인이 고른 얼굴상 (AI 평가 아님). 안 골랐으면 null */
  face_type: FaceType | null;
  /** 본인이 입력한 키 (cm). 안 적었으면 null */
  height_cm: number | null;
  interests: string[];
  appearance: Scores | null;
};

/** 얼굴상 목록 (2026-10-02). 서버 app/schemas/profile.py의 FACE_TYPES와 같아야 한다. 1개만 고른다. */
export const FACE_TYPES = ["강아지상", "고양이상", "여우상", "토끼상", "곰상", "공룡상", "사슴상", "늑대상", "다람쥐상", "햄스터상"] as const;
export type FaceType = (typeof FACE_TYPES)[number];
export const HEIGHT_MIN_CM = 140;
export const HEIGHT_MAX_CM = 210;

export type MyProfile = Card & {
  department_id: string | null;
  /** 본인 화면용 실제 이름 (card의 campus·department는 공개 설정에 따라 숨겨질 수 있음) */
  department_name: string | null;
  campus_name: string | null;
  show_department: boolean;
  /** null = 아직 고르지 않음 */
  show_campus: boolean | null;
  /** 학과를 한 번 정하면 바꿀 수 없음 (운영진에게 메일로 요청) */
  department_locked: boolean;
  campus_id: string;
};

export type Me = {
  email: string;
  status: string;
  university_id: string;
  onboarding: {
    profile_done: boolean;
    photo_status: "NOT_SUBMITTED" | "PENDING" | "IN_REVIEW" | "APPROVED" | "REJECTED" | "SUPERSEDED";
    preferences_done: boolean;
    photo_approved?: boolean;
    /** 첫 이용권 입금이 확인돼야 사진을 낼 수 있다 (2026-10-03). 유료화 끔·이미 낸 사람 → false */
    payment_required?: boolean;
    /** 가입 단계 표시에 "이용권"을 넣을지 (유료화를 켰고 테스트 계정이 아님) */
    pays_signup_fee?: boolean;
  };
  /** VIP (2026-10-03). visible = "받은 LIKE" 탭을 보여줄지 */
  vip?: { visible: boolean; active: boolean; until: string | null };
  /** 이용권 (2026-10-04 구독제) */
  membership?: Membership;
  /** 설문 (2026-10-05). pending = 설문을 받는 중이고 아직 안 답함 → 설문 화면만 보여준다 */
  survey?: { pending: boolean };
};

/** 이용권 상태 (2026-10-04 구독제). 기본 4주 / VIP 4주(기본 포함) */
export type Membership = {
  /** 유료화를 켰는가. false면 모두 무료로 쓴다 */
  enabled: boolean;
  /** 지금 추천·좋아요를 쓸 수 있는가 */
  active: boolean;
  /** 테스트 계정 (결제 없이 항상 이용) */
  free: boolean;
  /** none: 산 적 없음 / banked: 사진 검수가 끝나면 시작 / active / expired */
  status: "none" | "banked" | "active" | "expired";
  /** 끝나는 시각 (밤 12시, 한국 시간) */
  until: string | null;
  days_left: number | null;
  /** 아직 시작하지 않은 일수 (사진 검수 후 시작) */
  banked_days: number;
  days: number;
  price: number;
  /** 남은 날짜가 이 이하면 "○일 남았어요" 띠 */
  warn_days: number;
  /** 정식 오픈 시각 (점검 기간, 2026-10-04). 없으면 점검 없음 */
  open_at?: string | null;
  /** 지금 점검 기간인가 (추천·좋아요가 막히고 대화·결제만 됨) */
  before_open?: boolean;
};

/** GET /me/vip — VIP 안내·상태 (2026-10-03) */
export type VipInfo = {
  visible: boolean;
  active: boolean;
  /** 테스트 계정 (돈을 내지 않아도 항상 VIP) */
  tester: boolean;
  /** 돈을 내고 산 VIP가 끝나는 시각 */
  until: string | null;
  days: number;
  price: number;
  /** 지금 남은 기본 이용권 일수 (VIP를 사면 VIP가 끝난 뒤 이어서 씀) */
  member_days_left: number | null;
  daily_like_limit: number;
  base_like_limit: number;
  pass_cooldown_hours: number;
  base_pass_cooldown_hours: number;
  photo_resubmit_days: number;
  base_photo_resubmit_days: number;
  can_buy: boolean;
  blocked_reason: string | null;
  payment: PaymentDetail | null;
};

/** GET /liked-me — 나를 LIKE한 사람 (VIP 전용) */
export type LikedMeCard = Card & { liked_at: string; passed: boolean };

/** 결제 안내 한 건 (이용권·VIP 공통) */
export type PaymentDetail = Extract<PaymentInfo, { code: string }>;

/** 결제 안내가 들어 있는 응답인가 (유료화를 껐거나 테스트 계정이면 { required: false }만 온다) */
export function hasPayment(info: PaymentInfo): info is PaymentDetail {
  return "code" in info;
}

/** GET /me/payment — 기본 이용권 입금 안내 (2026-10-03, 2026-10-04 구독제: 첫 입금·연장 공통) */
export type PaymentInfo =
  | { required: false }
  | {
      /** 가입 단계의 첫 입금인가 (연장이면 false) */
      required: boolean;
      status: "CREATED" | "REQUESTED" | "REJECTED";
      amount: number;
      /** 입금자명에 실명 대신 적는 결제 코드 */
      code: string;
      open_now: boolean;
      open_hour: number;
      close_hour: number;
      /** 운영 시간 외에는 null (이미 "입금했어요"를 누른 사람은 보임) */
      bank_name: string | null;
      account_number: string | null;
      account_holder: string | null;
      support_email: string;
      membership?: Membership;
    };

export type Preferences = {
  configured: boolean;
  /** 가입할 때 정함. 본인은 못 바꾸고 운영진에게 메일로 요청 */
  preferred_gender: "MALE" | "FEMALE" | "ANY";
  gender_locked_message?: string;
  /** 나이 범위. null = 그쪽은 제한 없음. 둘 다 null = "나이 상관없음", max_age만 null = "35세 이상" */
  min_age: number | null;
  max_age: number | null;
  age_any?: boolean;
  /** 가로 바 양 끝 (서버 설정): 왼쪽 = 가입 가능한 최소 나이, 오른쪽 = "N세 이상" */
  age_floor?: number;
  age_cap?: number;
  campus_mode: "MY" | "ALL" | "SELECTED";
  campus_ids: string[];
  /** 같은 과 제외: 둘 중 한 명이라도 켰고 학과가 같으면 서로 추천되지 않음 */
  exclude_same_department: boolean;
  changes_left_today?: number;
  changes_per_day?: number;
};

export type MatchItem = {
  match_id: string;
  matched_at: string;
  partner: Card;
  last_message: { body: string; is_mine: boolean; sent_at: string } | null;
};

export type ChatMessage = { message_id: string; body: string; is_mine: boolean; sent_at: string };

export type Notification = {
  notification_id: string;
  type: string;
  title: string;
  body: string;
  related_id: string | null;
  read: boolean;
  created_at: string;
};

export const REPORT_REASONS: { value: string; label: string }[] = [
  { value: "SEXUAL_HARASSMENT", label: "성희롱" },
  { value: "ABUSIVE_LANGUAGE", label: "욕설" },
  { value: "THREAT", label: "협박" },
  { value: "STALKING", label: "스토킹" },
  { value: "OBSCENE_CONTENT", label: "음란물" },
  { value: "IMPERSONATION", label: "사칭" },
  { value: "MONEY_REQUEST", label: "금전 요구" },
  { value: "PERSONAL_INFO_REQUEST", label: "개인정보 요구" },
  { value: "SPAM", label: "스팸" },
  { value: "OTHER", label: "기타" },
];

export const GENDER_LABEL = { MALE: "남성", FEMALE: "여성", ANY: "상관없음" } as const;

/** 외모 등급 (상/중/하). 관리자 화면 전용 — 사용자 화면에는 절대 쓰지 않는다. */
export type AppearanceTier = "HIGH" | "MID" | "LOW";

export const TIER_OPTIONS: { value: AppearanceTier; label: string }[] = [
  { value: "HIGH", label: "상" },
  { value: "MID", label: "중" },
  { value: "LOW", label: "하" },
];

export const TIER_LABEL: Record<AppearanceTier, string> = { HIGH: "상", MID: "중", LOW: "하" };

/** 휴대폰 알림·메일 알림 설정 (2026-10-05, GET /me/alerts) */
export type Alerts = {
  /** 서버에 알림 열쇠가 들어 있어 휴대폰 알림을 쓸 수 있는가 */
  push_available: boolean;
  public_key: string | null;
  /** 알림을 켠 기기 수 (이 기기 포함 여부는 브라우저에 직접 확인) */
  device_count: number;
  /** 휴대폰 알림을 못 받을 때 학교 메일로 알려줄지 */
  email_notify: boolean;
};
