import { useEffect, useRef } from "react";

/**
 * 몇 초마다 fn을 실행한다. 단, 탭이 안 보일 때(다른 탭·앱으로 이동, 화면 꺼짐)는 멈춘다.
 * 다시 보이면 바로 한 번 실행하고 주기를 이어간다. → 아무도 안 보는 화면이 서버를 계속 부르지 않게.
 */
export function usePolling(fn: () => unknown, intervalMs: number, deps: React.DependencyList = []) {
  const fnRef = useRef(fn);
  useEffect(() => {
    fnRef.current = fn;
  }, [fn]);

  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | null = null;
    const run = () => {
      fnRef.current();
    };
    const start = () => {
      if (timer === null) timer = setInterval(run, intervalMs);
    };
    const stop = () => {
      if (timer !== null) clearInterval(timer);
      timer = null;
    };
    const onVisibility = () => {
      if (document.hidden) {
        stop();
      } else {
        run();
        start();
      }
    };

    run();
    if (!document.hidden) start();
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      stop();
      document.removeEventListener("visibilitychange", onVisibility);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intervalMs, ...deps]);
}
