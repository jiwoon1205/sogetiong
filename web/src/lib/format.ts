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
