"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PushPrompt } from "@/components/PushPrompt";
import { useSession } from "@/lib/session";

// 2026-10-25: 값이 "닫은 시각(밀리초)"으로 바뀌어서 키 이름도 바꾼다 (예전 값은 날짜 문자열이라 무시)
const CLOSED_KEY = "hufting:event-banner-closed-at";
/** ×를 누르고 이만큼 지나면 다시 뜬다 */
const HIDE_MS = 4 * 60 * 60 * 1000;

/** 마지막으로 ×를 누른 시각. 4시간이 지났거나 기록이 없으면 null */
function savedClosedAt(): number | null {
  try {
    const at = Number(localStorage.getItem(CLOSED_KEY));
    return Number.isFinite(at) && at > 0 && Date.now() - at < HIDE_MS ? at : null;
  } catch {
    return null;
  }
}

/** 머리말 바로 아래 한 줄 (2026-10-24).
 *  친구 초대 이벤트 기간에는 이벤트 줄을 보여주고, ×를 누르면 4시간 동안 숨긴다 → 4시간 뒤 다시 뜬다 (2026-10-25, 예전: 오늘만).
 *  이벤트가 아니거나 닫은 지 4시간이 안 됐으면 원래 자리의 휴대폰 알림 안내(PushPrompt)를 보여준다 (두 줄이 겹치지 않게). */
export function TopBanner() {
  const { me } = useSession();
  // ×를 누른 시각 (저장이 안 되는 브라우저에서도 이 화면에서는 4시간 숨김)
  const [closedAt, setClosedAt] = useState(savedClosedAt);
  const closed = closedAt !== null;
  // 화면을 켜 둔 채 4시간이 지나도 다시 뜨게 한다
  useEffect(() => {
    if (closedAt === null) return;
    const t = window.setTimeout(() => setClosedAt(null), Math.max(closedAt + HIDE_MS - Date.now(), 0));
    return () => window.clearTimeout(t);
  }, [closedAt]);
  // 화면을 연 시각 (이벤트가 끝난 뒤에도 화면을 켜 둔 경우를 위해 끝 시각과 비교. 서버의 active는 /me를 받을 때 값)
  const [openedAt] = useState(() => Date.now());
  const ev = me.referral_event;
  const running = !!ev?.active && (!ev.end || Date.parse(ev.end) > openedAt);

  if (!running || closed) return <PushPrompt />;

  function close() {
    const now = Date.now();
    try {
      localStorage.setItem(CLOSED_KEY, String(now));
    } catch {
      /* 저장이 안 되는 브라우저면 이 화면에서만 4시간 숨김 */
    }
    setClosedAt(now);
  }

  return (
    <div className="border-b border-line bg-paper-deep">
      <div className="mx-auto flex max-w-3xl items-center justify-between gap-3 px-5 py-2.5">
        <Link href="/settings#invite" className="min-w-0 text-[13.5px] leading-snug text-ink">
          🎁 친구 초대하면 <b className="font-semibold text-brick">슈퍼 라이크 1개</b>
          <span className="text-ink-faint"> · 11/6까지</span>{" "}
          <span className="whitespace-nowrap text-ink-soft underline underline-offset-2">내 링크 받기</span>
        </Link>
        <button onClick={close} aria-label="4시간 동안 숨기기" className="shrink-0 px-1 text-[18px] leading-none text-ink-faint hover:text-ink">
          ×
        </button>
      </div>
    </div>
  );
}
