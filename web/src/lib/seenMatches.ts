/** 매칭 축하 화면을 이 기기에서 이미 봤는지 기억한다 (브라우저 저장소, 2026-09-30).
 *
 *  - 내가 두 번째로 좋아요를 눌러 매칭되면 추천 화면에서 바로 축하 화면이 뜬다.
 *  - 상대가 나중에 좋아요를 눌러 매칭된 경우(나는 그 순간 화면에 없었음)는
 *    "대화" 목록에 들어갔을 때 아직 못 본 새 매칭이면 축하 화면을 한 번 보여준다.
 *  - 저장소를 못 쓰는 환경(사생활 보호 모드 등)이면 그냥 축하 화면을 건너뛴다.
 */

const KEY = "seen_matches_v1";
const LIMIT = 300; // 너무 많이 쌓이지 않게 최근 것만

function read(): string[] | null {
  try {
    const raw = window.localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as string[]) : null;
  } catch {
    return null;
  }
}

function write(ids: string[]) {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(ids.slice(-LIMIT)));
  } catch {}
}

export function markMatchSeen(...ids: string[]) {
  const seen = read() ?? [];
  write([...seen.filter((id) => !ids.includes(id)), ...ids]);
}

/** 아직 축하 화면을 안 본 매칭 id 목록.
 *  이 기기에서 처음 쓰는 경우(기록 없음)에는 지금 있는 매칭을 모두 "본 것"으로 처리하고 빈 목록을 돌려준다
 *  → 업데이트 직후 예전 매칭마다 축하 화면이 뜨는 일을 막는다. */
export function unseenMatches(ids: string[]): string[] {
  const seen = read();
  if (seen === null) {
    write(ids);
    return [];
  }
  return ids.filter((id) => !seen.includes(id));
}
