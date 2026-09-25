"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { PageTitle, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { cn, timeAgo } from "@/lib/format";
import type { Notification } from "@/lib/types";

function targetOf(n: Notification): string | null {
  if ((n.type === "MATCH_CREATED" || n.type === "NEW_MESSAGE") && n.related_id) return `/chat/${n.related_id}`;
  if (n.type === "PHOTO_REVIEWED") return "/profile";
  return null;
}

export default function NotificationsPage() {
  const router = useRouter();
  const [items, setItems] = useState<Notification[] | null>(null);

  useEffect(() => {
    api<{ notifications: Notification[] }>("/notifications").then((r) => setItems(r.notifications));
  }, []);

  async function open(n: Notification) {
    if (!n.read) {
      await api(`/notifications/${n.notification_id}`, { method: "PATCH", body: { read: true } }).catch(() => {});
      setItems((list) => list?.map((x) => (x.notification_id === n.notification_id ? { ...x, read: true } : x)) ?? null);
    }
    const to = targetOf(n);
    if (to) router.push(to);
  }

  if (!items) return <Spinner />;

  return (
    <div className="mx-auto max-w-app">
      <PageTitle eyebrow="알림" title="새로운 소식" />
      {items.length === 0 ? (
        <p className="py-10 text-center text-[14px] text-ink-faint">아직 알림이 없어요.</p>
      ) : (
        <ul className="divide-y divide-line border-y border-line">
          {items.map((n) => (
            <li key={n.notification_id}>
              <button onClick={() => open(n)} className="flex w-full gap-4 py-4 text-left hover:bg-paper-deep/60">
                <span className={cn("mt-2 h-1.5 w-1.5 shrink-0 rounded-full", n.read ? "bg-transparent" : "bg-brick")} aria-hidden />
                <span className="min-w-0 flex-1">
                  <span className="flex items-baseline justify-between gap-3">
                    <span className={cn("text-[15px]", n.read ? "text-ink-soft" : "font-semibold text-ink")}>{n.title}</span>
                    <span className="shrink-0 text-[12px] text-ink-faint">{timeAgo(n.created_at)}</span>
                  </span>
                  <span className="mt-0.5 block text-[13.5px] text-ink-soft">{n.body}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
