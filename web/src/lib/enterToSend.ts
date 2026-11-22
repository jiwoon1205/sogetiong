"use client";

import { useEffect, useRef } from "react";

/**
 * 입력칸에서 Enter = 보내기, Shift+Enter = 줄바꿈 (2026-11-22, 휴대폰·컴퓨터 모두).
 *
 * 한글은 글자를 조합하는 중에 Enter를 누르면 마지막 글자가 아직 확정되지 않았다
 * (예전에 휴대폰에서 "안녕하세" 와 "요" 가 따로 보내지던 문제).
 * 그래서 조합 중이면 바로 보내지 않고, 조합이 끝난 직후(compositionend)에 보낸다.
 *
 * 쓰는 법: <textarea {...enterToSend(send)} />
 */
export function useEnterToSend(send: () => void) {
  const sendAfterCompose = useRef(false);
  const sendRef = useRef(send);
  useEffect(() => {
    sendRef.current = send; // 늘 가장 최근의 보내기 함수 (입력한 글이 담긴)
  });

  return {
    enterKeyHint: "send" as const,
    onKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key !== "Enter" || e.shiftKey) return;
      e.preventDefault(); // 줄바꿈 대신 보내기
      if (e.nativeEvent.isComposing || e.keyCode === 229) {
        sendAfterCompose.current = true;
        return;
      }
      sendRef.current();
    },
    onCompositionEnd: () => {
      if (!sendAfterCompose.current) return;
      sendAfterCompose.current = false;
      // 확정된 마지막 글자가 입력값에 들어간 뒤에 보낸다
      setTimeout(() => sendRef.current(), 0);
    },
  };
}
