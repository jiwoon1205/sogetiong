"use client";

import Link from "next/link";
import { useState } from "react";
import { PushPrompt } from "@/components/PushPrompt";
import { useSession } from "@/lib/session";

const CLOSED_KEY = "hufting:event-banner-closed";

/** 한국 시간 오늘 날짜 "YYYY-MM-DD" */
function kstToday() {
  return new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Seoul" });
}

function closedToday(): boolean {
  try {
    return localStorage.getItem(CLOSED_KEY) === kstToday();
  } catch {
    return false;
  }
}

/** 머리말 바로 아래 한 줄 (2026-10-24).
 *  친구 초대 이벤트 기간에는 이벤트 줄을 보여주고, ×를 누르면 오늘(한국 시간)만 숨긴다 → 다음 날 다시 뜬다.
 *  이벤트가 아니거나 오늘 닫았으면 원래 자리의 휴대폰 알림 안내(PushPrompt)를 보여준다 (두 줄이 겹치지 않게). */
export function TopBanner() {
  const { me } = useSession();
  const [closed, setClosed] = useState(closedToday);
  // 화면을 연 시각 (이벤트가 끝난 뒤에도 화면을 켜 둔 경우를 위해 끝 시각과 비교. 서버의 active는 /me를 받을 때 값)
  const [openedAt] = useState(() => Date.now());
  const ev = me.referral_event;
  const running = !!ev?.active && (!ev.end || Date.parse(ev.end) > openedAt);

  if (!running || closed) return <PushPrompt />;

  function close() {
    try {
      localStorage.setItem(CLOSED_KEY, kstToday());
    } catch {
      /* 저장이 안 되는 브라우저면 이번에만 닫힘 */
    }
    setClosed(true);
  }

  return (
    <div className="border-b border-line bg-paper-deep">
      <div className="mx-auto flex max-w-3xl items-center justify-between gap-3 px-5 py-2.5">
        <Link href="/settings#invite" className="min-w-0 text-[13.5px] leading-snug text-ink">
          🎁 친구 초대하면 <b className="font-semibold text-brick">슈퍼 라이크 1개</b>
          <span className="text-ink-faint"> · 11/6까지</span>{" "}
          <span className="whitespace-nowrap text-ink-soft underline underline-offset-2">내 링크 받기</span>
        </Link>
        <button onClick={close} aria-label="오늘은 그만 보기" className="shrink-0 px-1 text-[18px] leading-none text-ink-faint hover:text-ink">
          ×
        </button>
      </div>
    </div>
  );
}
