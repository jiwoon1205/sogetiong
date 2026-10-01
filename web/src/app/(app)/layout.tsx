"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Brand } from "@/components/Brand";
import { Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { cn } from "@/lib/format";
import { usePolling } from "@/lib/polling";
import { SessionGate } from "@/lib/session";

const NAV = [
  { href: "/discover", label: "추천" },
  { href: "/matches", label: "대화" },
  { href: "/profile", label: "내 프로필" },
  { href: "/settings", label: "설정" },
];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <SessionGate fallback={<Spinner />}>
      <Shell>{children}</Shell>
    </SessionGate>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const [unread, setUnread] = useState(0);
  const inChat = path.startsWith("/chat/");

  // 안 읽은 알림 수: 20초마다 확인 (탭이 안 보이면 멈춤), 화면을 옮길 때도 확인
  // 알림 내용은 필요 없으니 개수만 받는다 (가벼운 요청)
  usePolling(
    () =>
      api<{ count: number }>("/notifications/unread-count")
        .then((r) => setUnread(r.count))
        .catch(() => {}),
    20000,
    [path],
  );

  // 채팅방은 화면 전체를 쓰는 별도 창이라 위쪽 머리말·아래 탭·여백을 그리지 않는다.
  // (예전에는 아래 탭을 숨겨도 그 자리 여백 pb-20(80px)이 남아서, 모바일에서 화면 전체가 한 번 더 스크롤되는 문제가 있었다)
  if (inChat) return <>{children}</>;

  return (
    <div className="min-h-dvh pb-20 sm:pb-0">
      <header className="sticky top-0 z-30 border-b border-line bg-paper/95 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-3xl items-center justify-between px-5">
          <Brand href="/discover" />
          <nav className="hidden items-center gap-6 sm:flex">
            {NAV.map((n) => (
              <Link key={n.href} href={n.href} className={cn("text-[14px] transition-colors", path.startsWith(n.href) ? "font-semibold text-ink" : "text-ink-soft hover:text-ink")}>
                {n.label}
              </Link>
            ))}
          </nav>
          <Link href="/notifications" className="inline-flex items-center gap-1.5 text-[14px] text-ink-soft hover:text-ink" aria-label={`알림 ${unread}개`}>
            알림
            {unread > 0 && <span className="num min-w-[18px] rounded-full bg-brick px-1.5 text-center text-[11px] font-semibold leading-[18px] text-paper">{unread > 99 ? "99+" : unread}</span>}
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-5 py-8 sm:py-12">{children}</main>

      {/* 모바일 하단 탭 */}
      <nav className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-4 border-t border-line bg-paper sm:hidden">
        {NAV.map((n) => (
          <Link key={n.href} href={n.href} className={cn("flex h-16 items-center justify-center text-[13px]", path.startsWith(n.href) ? "font-semibold text-ink" : "text-ink-faint")}>
            {n.label}
          </Link>
        ))}
      </nav>
    </div>
  );
}
