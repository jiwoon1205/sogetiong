"use client";

import { useState } from "react";

// 전체적인 인상 점수별 접속자 (2026-11-13, 관리자 현황).
// 남성·여성 그래프를 나란히 그리고, 점수(1~10)마다 "7일 이내 접속" 막대 안에 "오늘 접속" 막대를 겹쳐 그린다
// (오늘 접속한 사람은 7일 이내 접속에 포함되므로). 두 그래프는 세로축 눈금이 같아서 남녀를 바로 비교할 수 있다.
// 색: 청록(7일)·보라(오늘) — 색각 이상 검사 통과. 청록은 밝아서 숫자는 "표로 보기"와 마우스를 올린 설명으로 보완한다.
// 남녀 원그래프의 파랑·주황과 겹치지 않게 다른 색을 쓴다 (여기서 색은 성별이 아니라 기간을 뜻한다).

export type ImpressionBucket = { score: number; week: number; today: number };
export type ImpressionDistribution = { MALE: ImpressionBucket[]; FEMALE: ImpressionBucket[] };

const WEEK = { label: "7일 이내 접속", color: "#1baf7a" };
const TODAY = { label: "오늘 접속", color: "#6250d6" };
const SURFACE = "#FBFAF7"; // 카드 배경 (겹친 막대 사이 2px 테두리)

const W = 360;
const H = 200;
const PAD = { top: 12, right: 8, bottom: 26, left: 30 };
const PLOT_W = W - PAD.left - PAD.right;
const PLOT_H = H - PAD.top - PAD.bottom;

function niceMax(n: number): number {
  if (n <= 4) return 4;
  const step = Math.pow(10, Math.floor(Math.log10(n)));
  for (const m of [1, 2, 2.5, 5, 10]) {
    if (m * step >= n) return m * step;
  }
  return 10 * step;
}

// 위쪽만 4px 둥근 막대 (아래는 바닥선에 붙는다)
function barPath(x: number, y: number, w: number, h: number): string {
  if (h <= 0) return "";
  const r = Math.min(4, w / 2, h);
  return `M${x},${y + h} V${y + r} Q${x},${y} ${x + r},${y} H${x + w - r} Q${x + w},${y} ${x + w},${y + r} V${y + h} Z`;
}

function Panel({ title, buckets, max }: { title: string; buckets: ImpressionBucket[]; max: number }) {
  const [hover, setHover] = useState<number | null>(null);
  const slot = PLOT_W / buckets.length;
  const outerW = Math.min(22, slot - 6);
  const innerW = Math.max(4, outerW - 10);
  const y = (v: number) => PAD.top + PLOT_H - (v / max) * PLOT_H;
  const ticks = [0, max / 2, max];
  const totalWeek = buckets.reduce((a, b) => a + b.week, 0);
  const totalToday = buckets.reduce((a, b) => a + b.today, 0);
  const hovered = buckets.find((b) => b.score === hover);

  return (
    <div className="min-w-0 flex-1">
      <div className="mb-1 flex items-baseline justify-between gap-2">
        <p className="text-[13.5px] font-medium text-ink">{title}</p>
        <p className="num text-[12px] text-ink-faint">
          7일 {totalWeek.toLocaleString()}명 · 오늘 {totalToday.toLocaleString()}명
        </p>
      </div>
      <div className="relative">
        <svg viewBox={`0 0 ${W} ${H}`} className="block h-auto w-full" role="img" aria-label={`${title} 전체적인 인상 점수별 접속자`}>
          {ticks.map((t) => (
            <g key={t}>
              <line x1={PAD.left} x2={W - PAD.right} y1={y(t)} y2={y(t)} stroke="#DDD8CD" strokeWidth={t === 0 ? 1 : 0.5} />
              <text x={PAD.left - 6} y={y(t)} dy="0.32em" textAnchor="end" fontSize={10} fill="#8C887E" className="num">
                {Number.isInteger(t) ? t : t.toFixed(1)}
              </text>
            </g>
          ))}
          {buckets.map((b, i) => {
            const cx = PAD.left + slot * i + slot / 2;
            const active = hover === null || hover === b.score;
            return (
              <g key={b.score} opacity={active ? 1 : 0.4} className="transition-opacity">
                <path d={barPath(cx - outerW / 2, y(b.week), outerW, PAD.top + PLOT_H - y(b.week))} fill={WEEK.color} />
                <path
                  d={barPath(cx - innerW / 2, y(b.today), innerW, PAD.top + PLOT_H - y(b.today))}
                  fill={TODAY.color}
                  stroke={SURFACE}
                  strokeWidth={b.today > 0 ? 2 : 0}
                  paintOrder="stroke"
                />
                <text x={cx} y={H - 8} textAnchor="middle" fontSize={10.5} fill="#55524B" className="num">
                  {b.score}
                </text>
                {/* 막대보다 넓은 마우스 영역 */}
                <rect
                  x={cx - slot / 2}
                  y={PAD.top}
                  width={slot}
                  height={PLOT_H + 20}
                  fill="transparent"
                  onMouseEnter={() => setHover(b.score)}
                  onMouseLeave={() => setHover(null)}
                />
              </g>
            );
          })}
        </svg>
        {hovered && (
          <div
            className="pointer-events-none absolute top-0 z-10 -translate-x-1/2 rounded-md border border-line bg-paper-card px-3 py-2 text-[12px] shadow-sm"
            style={{ left: `${((PAD.left + slot * (hovered.score - 1) + slot / 2) / W) * 100}%` }}
          >
            <p className="font-medium text-ink">{hovered.score}점</p>
            <p className="num text-ink-soft">
              {WEEK.label} {hovered.week.toLocaleString()}명
            </p>
            <p className="num text-ink-soft">
              {TODAY.label} {hovered.today.toLocaleString()}명
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

export default function ImpressionChart({ data }: { data: ImpressionDistribution }) {
  const [table, setTable] = useState(false);
  const max = niceMax(Math.max(1, ...data.MALE.map((b) => b.week), ...data.FEMALE.map((b) => b.week)));
  const panels = [
    { key: "MALE", title: "남성", buckets: data.MALE },
    { key: "FEMALE", title: "여성", buckets: data.FEMALE },
  ] as const;

  return (
    <section className="mt-8">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-[14px] font-medium text-ink-soft">전체적인 인상 점수별 접속자</h2>
          <p className="mt-0.5 text-[12px] text-ink-faint">가장 최근 평가 기준 · 7일 이내 접속은 활성 사용자와 같은 기준(사진 검수 완료)</p>
        </div>
        <div className="flex items-center gap-4 text-[12.5px]">
          {[WEEK, TODAY].map((s) => (
            <span key={s.label} className="flex items-center gap-1.5 text-ink-soft">
              <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: s.color }} />
              {s.label}
            </span>
          ))}
          <button type="button" onClick={() => setTable((v) => !v)} className="text-ink-faint underline-offset-4 hover:underline">
            {table ? "그래프로 보기" : "표로 보기"}
          </button>
        </div>
      </div>
      <div className="rounded-card border border-line bg-paper-card p-5">
        {table ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[30rem] text-[13px]">
              <thead className="border-b border-line text-ink-faint">
                <tr>
                  <th className="py-2 pr-3 text-left font-normal">점수</th>
                  <th className="px-3 py-2 text-right font-normal">남 · 7일</th>
                  <th className="px-3 py-2 text-right font-normal">남 · 오늘</th>
                  <th className="px-3 py-2 text-right font-normal">여 · 7일</th>
                  <th className="py-2 pl-3 text-right font-normal">여 · 오늘</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {data.MALE.map((m, i) => {
                  const f = data.FEMALE[i];
                  return (
                    <tr key={m.score} className="num">
                      <td className="py-1.5 pr-3">{m.score}점</td>
                      <td className="px-3 py-1.5 text-right">{m.week}</td>
                      <td className="px-3 py-1.5 text-right">{m.today}</td>
                      <td className="px-3 py-1.5 text-right">{f?.week ?? 0}</td>
                      <td className="py-1.5 pl-3 text-right">{f?.today ?? 0}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="flex flex-col gap-6 md:flex-row">
            {panels.map((p) => (
              <Panel key={p.key} title={p.title} buckets={p.buckets} max={max} />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
