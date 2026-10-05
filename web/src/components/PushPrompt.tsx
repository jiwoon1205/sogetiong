"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { currentSubscription, detectEnv, permission, syncPush } from "@/lib/push";
import type { Alerts } from "@/lib/types";

const DISMISS_KEY = "push-prompt-dismissed-at";
const DISMISS_DAYS = 14;

function dismissedRecently(): boolean {
  try {
    const at = Number(localStorage.getItem(DISMISS_KEY) || 0);
    return Date.now() - at < DISMISS_DAYS * 24 * 60 * 60 * 1000;
  } catch {
    return false;
  }
}

/**
 * 머리말 아래 한 줄 안내 (2026-10-05): "새 메시지를 휴대폰 알림으로 받아보세요".
 * - 이 기기에서 알림을 아직 안 켠 사람에게만. 닫으면 14일 동안 안 보인다.
 * - 화면이 열릴 때 이미 켜진 알림은 지금 로그인에 다시 묶어 둔다 (syncPush).
 */
export function PushPrompt() {
  const [show, setShow] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      const alerts = await api<Alerts>("/me/alerts").catch(() => null);
      if (!alerts?.push_available) return;
      if (await syncPush(alerts).catch(() => false)) return; // 이미 켜져 있음
      const sub = await currentSubscription().catch(() => null);
      const env = detectEnv();
      if (!alive || sub || env === "unsupported" || permission() === "denied" || dismissedRecently()) return;
      setShow(true);
    })();
    return () => {
      alive = false;
    };
  }, []);

  if (!show) return null;

  function close() {
    try {
      localStorage.setItem(DISMISS_KEY, String(Date.now()));
    } catch {
      /* 저장이 안 되는 브라우저면 이번에만 닫힘 */
    }
    setShow(false);
  }

  return (
    <div className="border-b border-line bg-paper-deep">
      <div className="mx-auto flex max-w-3xl items-center justify-between gap-3 px-5 py-2.5">
        <Link href="/settings#alerts" className="min-w-0 text-[13.5px] text-ink" onClick={close}>
          🔔 새 메시지를 <b className="font-semibold">휴대폰 알림</b>으로 받아보세요 <span className="whitespace-nowrap text-ink-soft underline underline-offset-2">켜는 방법</span>
        </Link>
        <button onClick={close} aria-label="안내 닫기" className="shrink-0 px-1 text-[18px] leading-none text-ink-faint hover:text-ink">
          ×
        </button>
      </div>
    </div>
  );
}
