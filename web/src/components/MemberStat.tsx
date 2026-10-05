"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

// 머리말 로고 옆의 작은 숫자 (2026-10-05)
// - 위 줄: 전체 가입자 수 (서버가 5분마다 새로 센다)
// - 아래 줄: 활성 사용자(사진 검수 완료 + 최근 7일 접속) 성비. 얇은 막대 + "여 48 · 남 52"
// 숫자를 못 받아오면(서버 문제 등) 아무것도 그리지 않는다 → 화면이 깨지지 않게.

type Stats = { total: number; female_pct: number | null; male_pct: number | null };

export function MemberStat() {
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    let alive = true;
    api<Stats>("/stats/members")
      .then((s) => alive && setStats(s))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  if (!stats || stats.total <= 0) return null;
  const { total, female_pct: f, male_pct: m } = stats;

  return (
    <div
      className="flex animate-fadein flex-col justify-center gap-[5px] whitespace-nowrap border-l border-line pl-3 leading-none"
      aria-label={`함께하는 외대생 ${total}명${f !== null ? `, 활동 중인 사람 성비 여 ${f}% 남 ${m}%` : ""}`}
    >
      <span className="text-[11px] text-ink-faint">
        <span className="hidden min-[400px]:inline">함께하는 </span>외대생{" "}
        <span className="num font-serif text-[12px] font-semibold text-ink-soft">{total.toLocaleString("ko-KR")}</span>명
      </span>
      {f !== null && m !== null && (
        <span className="flex items-center gap-1.5 text-[10.5px] text-ink-faint" aria-hidden>
          <span className="flex h-[3px] w-7 overflow-hidden rounded-full bg-line-strong">
            <span className="h-full bg-brick/70" style={{ width: `${f}%` }} />
          </span>
          <span className="num">
            여 {f} · 남 {m}
          </span>
        </span>
      )}
    </div>
  );
}
