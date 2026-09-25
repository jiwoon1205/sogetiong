"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Brand } from "@/components/Brand";
import { Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { cn } from "@/lib/format";
import { SessionGate } from "@/lib/session";
import type { Notification } from "@/lib/types";

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

  useEffect(() => {
    const load = () =>
      api<{ notifications: Notification[] }>("/notifications?unread_only=true")
        .then((r) => setUnread(r.notifications.length))
        .catch(() => {});
    load();
    const t = setInterval(load, 20000);
    return () => clearInterval(t);
  }, [path]);

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
            {unread > 0 && <span className="num min-w-[18px] rounded-full bg-brick px-1.5 text-center text-[11px] font-semibold leading-[18px] text-paper">{unread}</span>}
          </Link>
        </div>
      </header>

      <main className={cn("mx-auto max-w-3xl px-5", inChat ? "py-0" : "py-8 sm:py-12")}>{children}</main>

      {/* 모바일 하단 탭 */}
      {!inChat && (
        <nav className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-4 border-t border-line bg-paper sm:hidden">
          {NAV.map((n) => (
            <Link key={n.href} href={n.href} className={cn("flex h-16 items-center justify-center text-[13px]", path.startsWith(n.href) ? "font-semibold text-ink" : "text-ink-faint")}>
              {n.label}
            </Link>
          ))}
        </nav>
      )}
    </div>
  );
}
