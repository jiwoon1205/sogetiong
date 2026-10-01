"use client";

import { useState } from "react";

// 활성 사용자(사진 검수 완료 + 최근 7일 접속) 남녀 분포 — 관리자 대시보드용 작은 원그래프.
// 색은 색각 이상(색맹)이 있어도 구분되는 파랑/주황 조합 (검사 스크립트로 확인함).
// 색만으로 구분하지 않도록 옆에 이름·숫자·비율을 같이 적는다.

const SLICES = [
  { key: "male", label: "남자", color: "#2a78d6" },
  { key: "female", label: "여자", color: "#eb6834" },
] as const;

const SIZE = 88; // 그래프 지름(px)
const R = SIZE / 2;
const GAP = "#FBFAF7"; // 조각 사이 2px 틈 = 카드 배경색

function slicePath(start: number, end: number): string {
  // 0 = 12시 방향, 시계 방향
  const p = (a: number) => [R + R * Math.sin(a), R - R * Math.cos(a)];
  const [x1, y1] = p(start);
  const [x2, y2] = p(end);
  const large = end - start > Math.PI ? 1 : 0;
  return `M${R},${R} L${x1},${y1} A${R},${R} 0 ${large} 1 ${x2},${y2} Z`;
}

export default function GenderPie({ male, female }: { male: number; female: number }) {
  const [hover, setHover] = useState<string | null>(null);
  const total = male + female;
  const values: Record<string, number> = { male, female };
  const pct = (n: number) => (total ? Math.round((n / total) * 100) : 0);

  let angle = 0;
  const arcs = SLICES.map((s) => {
    const sweep = total ? (values[s.key] / total) * Math.PI * 2 : 0;
    const arc = { ...s, value: values[s.key], start: angle, end: angle + sweep };
    angle += sweep;
    return arc;
  }).filter((a) => a.value > 0);

  return (
    <div className="flex items-center gap-5 rounded-card border border-line bg-paper-card px-5 py-4">
      <div>
        <p className="text-[13px] text-ink-soft">활성 사용자 남녀 분포</p>
        <p className="mt-0.5 text-[12px] text-ink-faint">사진 검수 완료 · 최근 7일 접속</p>
      </div>
      {total === 0 ? (
        <p className="text-[13px] text-ink-faint">아직 데이터가 없어요.</p>
      ) : (
        <>
          <svg
            width={SIZE}
            height={SIZE}
            viewBox={`0 0 ${SIZE} ${SIZE}`}
            role="img"
            aria-label={`남자 ${male}명(${pct(male)}%), 여자 ${female}명(${pct(female)}%)`}
            className="shrink-0"
          >
            {arcs.length === 1 ? (
              // 한쪽만 있으면 꽉 찬 원
              <circle cx={R} cy={R} r={R} fill={arcs[0].color}>
                <title>{`${arcs[0].label} ${arcs[0].value}명 (100%)`}</title>
              </circle>
            ) : (
              arcs.map((a) => (
                <path
                  key={a.key}
                  d={slicePath(a.start, a.end)}
                  fill={a.color}
                  stroke={GAP}
                  strokeWidth={2}
                  strokeLinejoin="round"
                  opacity={hover && hover !== a.key ? 0.45 : 1}
                  onMouseEnter={() => setHover(a.key)}
                  onMouseLeave={() => setHover(null)}
                  className="cursor-default transition-opacity"
                >
                  <title>{`${a.label} ${a.value}명 (${pct(a.value)}%)`}</title>
                </path>
              ))
            )}
          </svg>
          <ul className="space-y-1.5 text-[13px]">
            {SLICES.map((s) => (
              <li
                key={s.key}
                className="flex items-center gap-2"
                onMouseEnter={() => setHover(s.key)}
                onMouseLeave={() => setHover(null)}
              >
                <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: s.color }} />
                <span className="text-ink-soft">{s.label}</span>
                <span className="num font-semibold text-ink">{values[s.key].toLocaleString()}명</span>
                <span className="num text-ink-faint">{pct(values[s.key])}%</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
