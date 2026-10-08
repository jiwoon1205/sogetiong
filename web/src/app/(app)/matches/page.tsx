"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Initial } from "@/components/Initial";
import { MatchCelebration } from "@/components/MatchCelebration";
import { ReportModal } from "@/components/ReportModal";
import { ButtonLink, Notice, PageTitle, Spinner } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { timeAgo } from "@/lib/format";
import { usePolling } from "@/lib/polling";
import { markMatchSeen, unseenMatches } from "@/lib/seenMatches";
import type { MatchItem } from "@/lib/types";

type EndedMatch = { match_id: string; partner_nickname: string; matched_at: string; ended_at: string | null; report_pending: boolean };

export default function MatchesPage() {
  const [items, setItems] = useState<MatchItem[] | null>(null);
  const [error, setError] = useState("");

  const [ended, setEnded] = useState<EndedMatch[]>([]);
  const [reporting, setReporting] = useState<string | null>(null);
  // 내가 없을 때 생긴 새 매칭 (상대가 나중에 좋아요를 누른 경우) → 축하 화면 한 번
  const [celebrate, setCelebrate] = useState<MatchItem | null>(null);

  useEffect(() => {
    api<{ matches: MatchItem[] }>("/matches")
      .then((r) => {
        setItems(r.matches);
        const fresh = unseenMatches(r.matches.map((m) => m.match_id));
        // 여러 개면 가장 최근 것 하나만 보여주고 나머지도 본 것으로 처리
        const newest = r.matches.find((m) => fresh.includes(m.match_id));
        if (newest) setCelebrate(newest);
        if (fresh.length) markMatchSeen(...fresh);
      })
      .catch((e) => setError(errorMessage(e)));
    api<{ matches: EndedMatch[] }>("/matches/ended")
      .then((r) => setEnded(r.matches))
      .catch(() => {});
  }, []);

  // 목록을 열어 둔 동안 새 메시지(안 읽은 수·마지막 메시지·순서)를 15초마다 새로 받는다 (2026-10-08)
  usePolling(
    () =>
      api<{ matches: MatchItem[] }>("/matches")
        .then((r) => setItems(r.matches))
        .catch(() => {}),
    15000,
    [],
  );

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
          {items.map((m) => {
            // 안 읽은 메시지 (2026-10-08): 카톡처럼 오른쪽에 숫자 배지, 마지막 메시지를 진하게
            const unread = m.unread_count ?? 0;
            return (
              <li key={m.match_id}>
                <Link href={`/chat/${m.match_id}`} className="flex items-center gap-4 py-4 transition-colors hover:bg-paper-deep/60">
                  <Initial name={m.partner.nickname} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-baseline justify-between gap-3">
                      <p className="truncate text-[15.5px] font-semibold">{m.partner.nickname}</p>
                      <p className={unread ? "shrink-0 text-[12px] font-semibold text-brick" : "shrink-0 text-[12px] text-ink-faint"}>
                        {timeAgo(m.last_message?.sent_at ?? m.matched_at)}
                      </p>
                    </div>
                    <div className="mt-0.5 flex items-center justify-between gap-3">
                      <p className={unread ? "truncate text-[13.5px] font-semibold text-ink" : "truncate text-[13.5px] text-ink-soft"}>
                        {m.last_message ? `${m.last_message.is_mine ? "나: " : ""}${m.last_message.body}` : "새로운 매칭 — 먼저 인사해보세요"}
                      </p>
                      {unread > 0 && (
                        <span
                          aria-label={`안 읽은 메시지 ${unread}개`}
                          className="num flex h-5 min-w-5 shrink-0 items-center justify-center rounded-full bg-brick px-1.5 text-[11.5px] font-semibold leading-none text-paper"
                        >
                          {unread > 99 ? "99+" : unread}
                        </span>
                      )}
                    </div>
                  </div>
                </Link>
              </li>
            );
          })}
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

      {celebrate && <MatchCelebration partnerName={celebrate.partner.nickname} matchId={celebrate.match_id} onClose={() => setCelebrate(null)} />}

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
