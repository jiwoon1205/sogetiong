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
  interests: string[];
  appearance: Scores | null;
};

export type MyProfile = Card & {
  department_id: string | null;
  show_department: boolean;
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
  };
};

export type Preferences = {
  configured: boolean;
  preferred_gender: "MALE" | "FEMALE" | "ANY";
  min_age: number;
  max_age: number;
  campus_mode: "MY" | "ALL" | "SELECTED";
  campus_ids: string[];
  excluded_department_ids: string[];
  preferred_department_ids: string[];
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
