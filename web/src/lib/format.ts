// 서버(SQLite)가 시간대 표시 없이 "2026-09-30T01:00:00" 처럼 보내는 경우가 있다.
// 이 시간은 UTC인데, 브라우저는 표시가 없으면 한국 시간으로 읽어서 9시간이 어긋난다.
// 그래서 끝에 Z(=UTC)나 +09:00 같은 표시가 없으면 Z를 붙여서 UTC로 읽게 한다.
export function parseTime(iso: string): Date {
  const hasZone = /(Z|[+-]\d{2}:?\d{2})$/i.test(iso);
  return new Date(hasZone ? iso : `${iso}Z`);
}

export function timeAgo(iso: string): string {
  const then = parseTime(iso).getTime();
  const diff = Math.max(0, Date.now() - then) / 1000;
  if (diff < 60) return "방금";
  if (diff < 3600) return `${Math.floor(diff / 60)}분 전`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}시간 전`;
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)}일 전`;
  return parseTime(iso).toLocaleDateString("ko-KR", { month: "long", day: "numeric" });
}

export function clock(iso: string): string {
  return parseTime(iso).toLocaleTimeString("ko-KR", { hour: "numeric", minute: "2-digit" });
}

export function dateTime(iso: string): string {
  return parseTime(iso).toLocaleString("ko-KR", {
    year: "2-digit",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

/** 정식 오픈 시각 (점검 기간, 2026-10-04). 예: "10월 10일 오후 6시" */
export function openTime(iso: string): string {
  return parseTime(iso).toLocaleString("ko-KR", {
    timeZone: "Asia/Seoul",
    month: "long",
    day: "numeric",
    hour: "numeric",
    minute: parseTime(iso).getUTCMinutes() ? "2-digit" : undefined,
  });
}

/** 이용권이 끝나는 날 (2026-10-04). 서버는 "그날 밤 12시"(= 다음 날 0시, 한국 시간)를 보내므로 1초 빼서 그날로 보여준다.
 *  예: "11월 26일 밤 12시까지" */
export function untilDay(iso: string): string {
  const d = new Date(parseTime(iso).getTime() - 1000);
  const day = d.toLocaleDateString("ko-KR", { timeZone: "Asia/Seoul", month: "long", day: "numeric" });
  return `${day} 밤 12시까지`;
}

/** 한국 시간 날짜를 "YYYY-MM-DD"로 */
function kstDate(d: Date): string {
  return d.toLocaleDateString("en-CA", { timeZone: "Asia/Seoul" });
}

/** 할인 마감 D-Day (2026-10-07). 마감 시각(밤 12시 = 다음 날 0시)을 지난 마지막 날 기준.
 *  마지막 날이면 "D-Day", 하루 전이면 "D-1". 이미 끝났으면 null. */
export function dday(iso: string, now: Date = new Date()): string | null {
  const end = parseTime(iso);
  if (end.getTime() <= now.getTime()) return null;
  const last = kstDate(new Date(end.getTime() - 1000));
  const diff = Math.round((Date.parse(last) - Date.parse(kstDate(now))) / 86_400_000);
  return diff <= 0 ? "D-Day" : `D-${diff}`;
}

/** 할인 마감 안내. 예: "오늘 밤 12시 마감" / "10월 7일 밤 12시 마감" */
export function ddayEnd(iso: string, now: Date = new Date()): string {
  return dday(iso, now) === "D-Day" ? "오늘 밤 12시 마감" : untilDay(iso).replace("까지", " 마감");
}

/** 할인율 (내림). 예: 8,000원 → 3,000원 = 62 */
export function discountPercent(regular: number, price: number): number {
  return regular > 0 ? Math.floor(((regular - price) / regular) * 100) : 0;
}
