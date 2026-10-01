import { useEffect, useState } from "react";

/**
 * 지금 "눈에 보이는 화면" 크기를 알려준다 (모바일 키보드가 올라오면 높이가 줄어든다).
 *
 * 왜 필요한가: 모바일 브라우저는 키보드가 올라와도 100dvh 같은 CSS 높이를 줄이지 않는다.
 * 그래서 화면 높이에 맞춘 채팅창이 키보드에 가려지거나, 화면 전체가 위로 밀려 올라간다.
 * visualViewport는 키보드를 뺀 실제로 보이는 영역이라, 여기에 맞추면 입력창이 항상 키보드 바로 위에 붙는다.
 *
 * 반환값이 null이면(서버에서 그리는 중이거나 아주 오래된 브라우저) CSS 기본 높이를 쓴다.
 */
export function useVisualViewport() {
  const [vp, setVp] = useState<{ height: number; top: number } | null>(null);

  useEffect(() => {
    const vv = window.visualViewport;
    if (!vv) return;
    const update = () => {
      // 손가락으로 확대(핀치 줌)한 상태에서는 높이를 따라가지 않는다 (화면이 쪼그라드는 것 방지)
      if (vv.scale > 1.01) return;
      setVp({ height: Math.round(vv.height), top: Math.round(vv.offsetTop) });
    };
    update();
    vv.addEventListener("resize", update);
    vv.addEventListener("scroll", update);
    return () => {
      vv.removeEventListener("resize", update);
      vv.removeEventListener("scroll", update);
    };
  }, []);

  return vp;
}
