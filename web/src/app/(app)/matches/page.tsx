"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Initial } from "@/components/Initial";
import { ButtonLink, Notice, PageTitle, Spinner } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { timeAgo } from "@/lib/format";
import type { MatchItem } from "@/lib/types";

export default function MatchesPage() {
  const [items, setItems] = useState<MatchItem[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<{ matches: MatchItem[] }>("/matches")
      .then((r) => setItems(r.matches))
      .catch((e) => setError(errorMessage(e)));
  }, []);

  if (error) return <Notice tone="error">{error}</Notice>;
  if (!items) return <Spinner />;

  return (
    <div className="mx-auto max-w-app">
      <PageTitle eyebrow="대화" title="마음이 맞은 사람들" />
      {items.length === 0 ? (
        <div className="rounded-card border border-line bg-paper-card px-6 py-12 text-center">
          <p className="text-[15px] text-ink">아직 매칭된 사람이 없어요.</p>
          <p className="mt-2 text-[13.5px] text-ink-soft">서로 좋아요를 누르면 여기에서 대화를 시작할 수 있어요.</p>
          <ButtonLink href="/discover" variant="secondary" className="mt-6">
            추천 보러 가기
          </ButtonLink>
        </div>
      ) : (
        <ul className="divide-y divide-line border-y border-line">
          {items.map((m) => (
            <li key={m.match_id}>
              <Link href={`/chat/${m.match_id}`} className="flex items-center gap-4 py-4 transition-colors hover:bg-paper-deep/60">
                <Initial name={m.partner.nickname} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-baseline justify-between gap-3">
                    <p className="truncate text-[15.5px] font-semibold">{m.partner.nickname}</p>
                    <p className="shrink-0 text-[12px] text-ink-faint">{timeAgo(m.last_message?.sent_at ?? m.matched_at)}</p>
                  </div>
                  <p className="mt-0.5 truncate text-[13.5px] text-ink-soft">
                    {m.last_message ? `${m.last_message.is_mine ? "나: " : ""}${m.last_message.body}` : "새로운 매칭 — 먼저 인사해보세요"}
                  </p>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
