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
  };
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
