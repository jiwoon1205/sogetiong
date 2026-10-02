import { useEffect, useRef } from "react";

// 오늘 날짜 (한국 시간, "2026-10-02" 형태).
// 하루 제한(좋아요 5개, 매칭 조건 변경 3번)은 모두 한국 시간 자정에 다시 채워진다.
export function kstDay(): string {
  return new Date(Date.now() + 9 * 60 * 60 * 1000).toISOString().slice(0, 10);
}

/**
 * 화면을 띄워 둔 채 한국 날짜가 바뀌면 onNewDay를 부른다.
 *
 * 휴대폰에서 브라우저를 껐다가 다음 날 다시 켜면 페이지가 새로 열리지 않고 그대로 돌아온다.
 * 그러면 "오늘 남은 횟수"가 어제 숫자(0)로 멈춰 보인다 (2026-10-02 민원).
 * 그래서 화면으로 돌아왔을 때와 1분마다 날짜를 확인한다.
 */
export function useKstNewDay(onNewDay: () => void) {
  const loadedDay = useRef(kstDay());
  // 매번 새로 만들어지는 함수를 그때그때 기억해 둔다 (렌더 중이 아니라 effect 안에서 바꿔야 한다)
  const callback = useRef(onNewDay);
  useEffect(() => {
    callback.current = onNewDay;
  });

  useEffect(() => {
    const check = () => {
      if (document.visibilityState !== "visible") return;
      const today = kstDay();
      if (today !== loadedDay.current) {
        loadedDay.current = today;
        callback.current();
      }
    };
    document.addEventListener("visibilitychange", check);
    window.addEventListener("focus", check);
    window.addEventListener("pageshow", check);
    const timer = window.setInterval(check, 60_000);
    return () => {
      document.removeEventListener("visibilitychange", check);
      window.removeEventListener("focus", check);
      window.removeEventListener("pageshow", check);
      window.clearInterval(timer);
    };
  }, []);
}
