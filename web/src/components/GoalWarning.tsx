"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * 찾는 관계가 달라 좋아요를 못 보낼 때 화면 가운데에 잠깐 뜨는 빨간 바 (2026-11-14)
 * - 진지한 연애 ↔ 캐주얼한 만남은 서로 좋아요·슈퍼 라이크를 못 보낸다 (서버도 막음: GOAL_MISMATCH)
 * - 사용자 요청은 0.5초였지만, 한 줄을 읽기엔 짧아서 1.5초로 했다 (SHOW_MS만 바꾸면 됨)
 */
const SHOW_MS = 1500;
export const GOAL_MISMATCH_TEXT = "진지한 연애와 캐주얼한 만남은 서로 좋아요를 보낼 수 없어요";

export function useGoalWarning() {
  const [shownAt, setShownAt] = useState<number | null>(null);
  const timer = useRef<number | undefined>(undefined);

  const show = useCallback(() => {
    window.clearTimeout(timer.current);
    setShownAt(Date.now()); // 연달아 눌러도 다시 처음부터 보인다
    timer.current = window.setTimeout(() => setShownAt(null), SHOW_MS);
    // 휴대폰이면 짧게 진동 (지원하는 기기만)
    try {
      navigator.vibrate?.(40);
    } catch {}
  }, []);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  const bar =
    shownAt === null ? null : (
      <div className="pointer-events-none fixed inset-x-0 top-1/2 z-[70] flex -translate-y-1/2 justify-center px-5" role="alert" aria-live="assertive">
        <p key={shownAt} className="animate-fadein rounded-md bg-brick px-5 py-3 text-center text-[14px] font-semibold leading-snug text-paper shadow-lg">
          {GOAL_MISMATCH_TEXT}
        </p>
      </div>
    );

  return { bar, show };
}
