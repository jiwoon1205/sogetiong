// 게시판(자유·연애·캐주얼)·쪽지 (2026-11-22). 서버 규칙은 backend/app/services/board_service.py 맨 위.

export type BoardKey = "FREE" | "LOVE" | "CASUAL";

export type BoardAuthor = {
  id: string | null;
  nickname: string;
  has_avatar: boolean;
  avatar_version?: string | null;
  gender: "MALE" | "FEMALE" | null;
  school: string | null;
  campus: string | null;
  score: { key: string; label: string; value: number } | null;
  deleted: boolean;
};

export type MyBoardProfile = BoardAuthor & {
  shown_score: string | null;
  next_nickname_change: string;
  banned_until: string | null;
  ban_permanent: boolean;
  ban_reason: string | null;
};

export type BoardInfo = { key: BoardKey; name: string; allowed: boolean; sexual_rule: string | null };

export type BoardMe = {
  profile: MyBoardProfile | null;
  can_create: boolean;
  cannot_create_reason: string | null;
  boards: BoardInfo[];
  my_scores: Record<string, number> | null;
  score_labels: Record<string, string>;
  free_notes_left: number | null;
  super_likes: { count: number; price: number };
  unread_notes: number;
  config: {
    sexual_rule: string;
    nickname_min: number;
    nickname_max: number;
    title_max: number;
    body_max: number;
    comment_max: number;
    note_max: number;
    daily_posts: number;
    free_notes_per_day: number;
    super_like_price: number;
  };
};

export type BoardPost = {
  id: string;
  board: BoardKey;
  title: string;
  body: string;
  author: BoardAuthor;
  mine: boolean;
  hidden: boolean;
  comment_count: number;
  created_at: string;
};

export type BoardComment = {
  id: string;
  body: string;
  author: BoardAuthor;
  mine: boolean;
  by_post_author: boolean;
  hidden: boolean;
  created_at: string;
};

export type NoteRoom = {
  id: string;
  partner: BoardAuthor;
  i_started: boolean;
  closed: boolean;
  can_send: boolean;
  cannot_send_reason: "CLOSED" | "WAIT_REPLY" | "PARTNER_GONE" | null;
  waiting_reply: boolean;
  unread: number;
  last_message: string | null;
  last_message_mine: boolean;
  last_message_at: string;
};

export type NoteMessage = { id: string; body: string; mine: boolean; created_at: string };

export const BOARD_NAMES: Record<BoardKey, string> = { FREE: "자유", LOVE: "연애", CASUAL: "캐주얼" };

export const BOARD_REPORT_REASONS: { value: string; label: string }[] = [
  { value: "ABUSE", label: "욕설·비하" },
  { value: "SEXUAL", label: "성적인 이야기" },
  { value: "OBSCENE", label: "음란·부적절한 사진" },
  { value: "SPAM", label: "광고·도배" },
  { value: "PERSONAL_INFO", label: "개인정보 노출" },
  { value: "OTHER", label: "기타" },
];

export function avatarUrl(author: Pick<BoardAuthor, "id" | "has_avatar" | "avatar_version">): string | null {
  if (!author.id || !author.has_avatar) return null;
  return `/api/v1/board/avatars/${author.id}?v=${encodeURIComponent(author.avatar_version ?? "")}`;
}

export function banText(p: Pick<MyBoardProfile, "banned_until" | "ban_permanent">): string {
  if (!p.banned_until) return "";
  if (p.ban_permanent) return "영구 정지";
  const d = new Date(p.banned_until);
  return `${d.toLocaleDateString("ko-KR", { month: "long", day: "numeric" })} ${d.toLocaleTimeString("ko-KR", { hour: "numeric", minute: "2-digit" })}까지`;
}
