"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Initial } from "@/components/Initial";
import { ReportModal } from "@/components/ReportModal";
import { ButtonLink, Notice, PageTitle, Spinner } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { timeAgo } from "@/lib/format";
import type { MatchItem } from "@/lib/types";

type EndedMatch = { match_id: string; partner_nickname: string; matched_at: string; ended_at: string | null; report_pending: boolean };

export default function MatchesPage() {
  const [items, setItems] = useState<MatchItem[] | null>(null);
  const [error, setError] = useState("");

  const [ended, setEnded] = useState<EndedMatch[]>([]);
  const [reporting, setReporting] = useState<string | null>(null);

  useEffect(() => {
    api<{ matches: MatchItem[] }>("/matches")
      .then((r) => setItems(r.matches))
      .catch((e) => setError(errorMessage(e)));
    api<{ matches: EndedMatch[] }>("/matches/ended")
      .then((r) => setEnded(r.matches))
      .catch(() => {});
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

      {ended.length > 0 && (
        <section className="mt-12">
          <p className="eyebrow mb-1">끝난 대화</p>
          <p className="mb-4 text-[13px] text-ink-faint">대화가 끝났거나 상대가 탈퇴했어도, 불쾌한 일이 있었다면 신고할 수 있어요. (최근 90일)</p>
          <ul className="divide-y divide-line border-y border-line">
            {ended.map((m) => (
              <li key={m.match_id} className="flex items-center gap-4 py-3.5">
                <Initial name={m.partner_nickname} size={32} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[14.5px] text-ink-soft">{m.partner_nickname}</p>
                  <p className="text-[12px] text-ink-faint">{m.ended_at ? `${timeAgo(m.ended_at)} 종료` : "종료됨"}</p>
                </div>
                {m.report_pending ? (
                  <span className="text-[13px] text-ink-faint">신고 접수됨</span>
                ) : (
                  <button onClick={() => setReporting(m.match_id)} className="text-[13px] text-brick underline underline-offset-4">
                    신고하기
                  </button>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {reporting && (
        <ReportModal
          open
          matchId={reporting}
          onClose={() => setReporting(null)}
          onDone={() => setEnded((list) => list.map((m) => (m.match_id === reporting ? { ...m, report_pending: true } : m)))}
        />
      )}
    </div>
  );
}
