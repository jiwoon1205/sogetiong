/** 친구 초대 링크 코드 기억하기 (2026-10-24).
 *  ?ref=K7PX2M 로 들어오면 30일 동안 이 브라우저에 기억 → 나중에 가입해도 함께 보낸다.
 *  코드가 틀렸거나 이벤트 기간이 아니면 서버가 조용히 무시한다. */

const KEY = "hufting:ref";
const KEEP_DAYS = 30;

export function saveRefFromUrl() {
  try {
    const code = new URLSearchParams(window.location.search).get("ref");
    if (!code || !/^[A-Za-z0-9]{6}$/.test(code)) return;
    window.localStorage.setItem(KEY, JSON.stringify({ code: code.toUpperCase(), at: Date.now() }));
  } catch {
    /* 저장이 안 되는 브라우저면 넘어간다 */
  }
}

export function savedRef(): string | null {
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return null;
    const { code, at } = JSON.parse(raw) as { code: string; at: number };
    if (Date.now() - at > KEEP_DAYS * 86_400_000) return null;
    return code;
  } catch {
    return null;
  }
}
