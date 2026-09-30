"use client";

import { useRef, useState } from "react";
import { cn } from "@/lib/format";

/** 나이 범위를 고르는 가로 바 (손잡이 2개).
 *
 *  - 두 손잡이는 서로 넘어가지 않는다 (최소 ≤ 최대, 같은 나이도 가능)
 *  - 오른쪽 끝(cap)은 "N세 이상"을 뜻한다 → 저장할 때 최대 나이를 비운다 (PreferencesForm에서 처리)
 *  - 손가락으로 잡기 쉽게 손잡이를 누르는 영역은 44px
 *  - 키보드: ←/→(또는 ↓/↑) 1살씩, PageDown/PageUp 5살씩, Home/End 양 끝
 */
export function AgeRangeSlider({
  floor,
  cap,
  value,
  onChange,
  disabled = false,
}: {
  floor: number;
  cap: number;
  value: [number, number];
  onChange: (next: [number, number]) => void;
  disabled?: boolean;
}) {
  const trackRef = useRef<HTMLDivElement>(null);
  // 지금 끌고 있는 손잡이 (0 = 최소, 1 = 최대)
  // "pending" = 두 손잡이가 겹친 곳을 잡음 → 처음 움직이는 방향을 보고 어느 쪽인지 정한다
  const [dragging, setDragging] = useState<0 | 1 | "pending" | null>(null);
  const [lo, hi] = value;
  const span = Math.max(1, cap - floor);
  const pct = (v: number) => ((v - floor) / span) * 100;

  function clamp(v: number) {
    return Math.min(cap, Math.max(floor, Math.round(v)));
  }

  /** 한쪽 손잡이를 옮긴다. 다른 손잡이를 넘어가지 않게 막는다. */
  function move(which: 0 | 1, v: number) {
    const next = clamp(v);
    if (which === 0) {
      const nlo = Math.min(next, hi);
      if (nlo !== lo) onChange([nlo, hi]);
    } else {
      const nhi = Math.max(next, lo);
      if (nhi !== hi) onChange([lo, nhi]);
    }
  }

  function valueAt(clientX: number) {
    const rect = trackRef.current?.getBoundingClientRect();
    if (!rect || rect.width === 0) return lo;
    const ratio = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
    return floor + ratio * span;
  }

  function onPointerDown(e: React.PointerEvent<HTMLDivElement>) {
    if (disabled || (e.pointerType === "mouse" && e.button !== 0)) return;
    const v = valueAt(e.clientX);
    e.currentTarget.setPointerCapture(e.pointerId);
    e.preventDefault();
    // 두 손잡이가 겹친 곳을 잡았으면: 양 끝이면 움직일 수 있는 쪽, 아니면 처음 움직이는 방향으로 정한다
    if (lo === hi && Math.abs(v - lo) < 0.5) {
      if (lo >= cap) return startDrag(e, 0);
      if (lo <= floor) return startDrag(e, 1);
      setDragging("pending");
      return;
    }
    // 누른 곳에서 더 가까운 손잡이를 잡는다 (겹쳐 있으면 누른 쪽 방향으로)
    const which: 0 | 1 = lo === hi ? (v < lo ? 0 : 1) : Math.abs(v - lo) <= Math.abs(v - hi) ? 0 : 1;
    startDrag(e, which);
    move(which, v);
  }

  function startDrag(e: React.PointerEvent<HTMLDivElement>, which: 0 | 1) {
    setDragging(which);
    // 잡은 손잡이에 키보드 포커스도 옮겨 준다 (그다음 화살표 키로 미세 조정 가능)
    const thumb = e.currentTarget.querySelectorAll<HTMLElement>("[role=slider]")[which];
    thumb?.focus({ preventScroll: true });
  }

  function onPointerMove(e: React.PointerEvent<HTMLDivElement>) {
    if (dragging === null) return;
    const v = valueAt(e.clientX);
    if (dragging === "pending") {
      if (Math.abs(v - lo) < 0.5) return; // 아직 방향을 알 수 없음
      const which: 0 | 1 = v < lo ? 0 : 1;
      startDrag(e, which);
      move(which, v);
      return;
    }
    move(dragging, v);
  }

  function endDrag(e: React.PointerEvent<HTMLDivElement>) {
    if (dragging === null) return;
    setDragging(null);
    if (e.currentTarget.hasPointerCapture(e.pointerId)) e.currentTarget.releasePointerCapture(e.pointerId);
  }

  function onKeyDown(which: 0 | 1, e: React.KeyboardEvent) {
    if (disabled) return;
    const current = which === 0 ? lo : hi;
    const steps: Record<string, number> = {
      ArrowLeft: current - 1,
      ArrowDown: current - 1,
      ArrowRight: current + 1,
      ArrowUp: current + 1,
      PageDown: current - 5,
      PageUp: current + 5,
      Home: floor,
      End: cap,
    };
    if (!(e.key in steps)) return;
    e.preventDefault();
    move(which, steps[e.key]);
  }

  const label = (v: number) => (v >= cap ? `${cap}세 이상` : `${v}세`);

  const thumb = (which: 0 | 1) => {
    const v = which === 0 ? lo : hi;
    return (
      <div
        role="slider"
        tabIndex={disabled ? -1 : 0}
        aria-label={which === 0 ? "최소 나이" : "최대 나이"}
        aria-valuemin={which === 0 ? floor : lo}
        aria-valuemax={which === 0 ? hi : cap}
        aria-valuenow={v}
        aria-valuetext={label(v)}
        aria-disabled={disabled || undefined}
        onKeyDown={(e) => onKeyDown(which, e)}
        className={cn(
          // 누르는 영역 44px, 보이는 손잡이는 22px
          "group absolute top-1/2 flex h-11 w-11 -translate-x-1/2 -translate-y-1/2 touch-none items-center justify-center rounded-full focus:outline-none",
          // 두 손잡이가 겹치면, 마지막으로 움직인 쪽이 위로 오게 (최소 손잡이가 오른쪽 끝에 붙으면 최소가 위)
          which === 0 && lo >= cap ? "z-20" : dragging === which ? "z-20" : "z-10",
          disabled ? "cursor-not-allowed" : "cursor-grab active:cursor-grabbing",
        )}
        style={{ left: `${pct(v)}%` }}
      >
        <span
          aria-hidden
          className={cn(
            "block h-[22px] w-[22px] rounded-full border-2 bg-paper-card shadow-[0_1px_3px_rgba(30,29,27,0.18)] transition-transform",
            "group-focus-visible:outline group-focus-visible:outline-2 group-focus-visible:outline-offset-2 group-focus-visible:outline-ink",
            disabled ? "border-line-strong" : "border-ink",
            dragging === which && "scale-110",
          )}
        />
      </div>
    );
  };

  return (
    <div className={cn("select-none", disabled && "opacity-40")}>
      <div
        ref={trackRef}
        className={cn("relative mx-[11px] h-11", disabled ? "pointer-events-none" : "cursor-pointer")}
        style={{ touchAction: "pan-y" }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
      >
        {/* 바 전체 */}
        <div aria-hidden className="absolute inset-x-0 top-1/2 h-[3px] -translate-y-1/2 rounded-full bg-line" />
        {/* 고른 구간 */}
        <div
          aria-hidden
          className={cn("absolute top-1/2 h-[3px] -translate-y-1/2 rounded-full", disabled ? "bg-line-strong" : "bg-ink")}
          style={{ left: `${pct(lo)}%`, width: `${pct(hi) - pct(lo)}%` }}
        />
        {thumb(0)}
        {thumb(1)}
      </div>
      <div aria-hidden className="flex justify-between text-[12px] text-ink-faint">
        <span className="num">{floor}세</span>
        <span className="num">{cap}세 이상</span>
      </div>
    </div>
  );
}
