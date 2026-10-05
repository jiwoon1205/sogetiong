/**
 * 백엔드 API 호출 도우미.
 *
 * - 로그인은 HttpOnly 쿠키로 자동 처리된다 (credentials: "include").
 * - 데이터를 바꾸는 요청(POST/PUT/PATCH/DELETE)에는 CSRF 토큰을 헤더에 붙인다.
 *   사용자는 csrf_token 쿠키, 관리자는 admin_csrf_token 쿠키를 쓴다.
 */

export class ApiError extends Error {
  status: number;
  code: string;
  constructor(status: number, message: string, code: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

type Options = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  form?: FormData;
  admin?: boolean;
  /** 화면을 닫는 중에도 요청이 끝까지 가게 (브라우저가 페이지를 정리해도 보냄) */
  keepalive?: boolean;
};

function readCookie(name: string): string | undefined {
  if (typeof document === "undefined") return undefined;
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : undefined;
}

const FIELD_NAMES: Record<string, string> = {
  email: "이메일",
  password: "비밀번호",
  new_password: "새 비밀번호",
  nickname: "닉네임",
  code: "인증번호",
  birth_date: "생년월일",
  bio: "자기소개",
  ideal_type: "이상형",
  body: "메시지",
  mbti: "MBTI",
  reason: "사유",
};

/** FastAPI 422 에러(배열)를 사람이 읽을 수 있는 한 문장으로 */
function explainValidation(detail: Array<{ msg?: string; loc?: string[]; type?: string }>): string {
  const first = detail[0] ?? {};
  const field = FIELD_NAMES[first.loc?.[first.loc.length - 1] ?? ""] ?? "입력값";
  const msg = (first.msg ?? "").replace(/^Value error, /, "");
  if (/[가-힣]/.test(msg)) return msg;
  switch (first.type) {
    case "string_too_short":
      return `${field}이(가) 너무 짧습니다.`;
    case "string_too_long":
      return `${field}이(가) 너무 깁니다.`;
    case "string_pattern_mismatch":
      return `${field} 형식을 확인해주세요.`;
    case "value_error":
      return `${field} 형식을 확인해주세요.`;
    case "missing":
      return `${field}을(를) 입력해주세요.`;
    default:
      return `${field}을(를) 다시 확인해주세요.`;
  }
}

export async function api<T = unknown>(path: string, opts: Options = {}): Promise<T> {
  const method = opts.method ?? "GET";
  const headers: Record<string, string> = {};
  if (method !== "GET") {
    const csrf = readCookie(opts.admin ? "admin_csrf_token" : "csrf_token");
    if (csrf) headers["X-CSRF-Token"] = csrf;
  }
  let body: BodyInit | undefined;
  if (opts.form) {
    body = opts.form;
  } else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }

  let res: Response;
  try {
    res = await fetch(`/api/v1${path}`, { method, headers, body, credentials: "include", cache: "no-store", keepalive: opts.keepalive });
  } catch {
    throw new ApiError(0, "서버에 연결할 수 없습니다. 백엔드가 켜져 있는지 확인해주세요.", "NETWORK");
  }

  const text = await res.text();
  const data = text ? safeJson(text) : null;
  if (!res.ok) {
    const detail = data && typeof data === "object" ? (data as { detail?: unknown }).detail : undefined;
    let message = "요청을 처리하지 못했습니다.";
    let code = String(res.status);
    if (Array.isArray(detail)) message = explainValidation(detail);
    else if (typeof detail === "string") {
      message = detail;
      if (/^[A-Z_]+$/.test(detail)) code = detail;
    }
    if (res.status >= 500) message = "서버에 문제가 생겼습니다. 잠시 후 다시 시도해주세요.";
    throw new ApiError(res.status, message, code);
  }
  return data as T;
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

/** 서버가 코드(영문 대문자)로만 알려 주는 에러를 문장으로 */
const CODE_MESSAGES: Record<string, string> = {
  PAYMENT_REQUIRED: "이용권 입금이 확인된 뒤에 사진을 제출할 수 있어요.",
  MEMBERSHIP_REQUIRED: "이용권이 끝났어요. 이용권을 연장하면 다시 이용할 수 있어요. 대화는 계속할 수 있어요.",
  // 점검 기간 (2026-10-04): 정식 오픈 전에는 추천·좋아요·받은 LIKE·사진 재검토가 막힌다
  MAINTENANCE: "지금은 정식 오픈 전 점검 기간이에요. 오픈하면 바로 이용할 수 있어요. 대화와 이용권 결제는 지금도 돼요.",
};

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) return CODE_MESSAGES[err.code] ?? err.message;
  return "알 수 없는 문제가 생겼습니다.";
}
