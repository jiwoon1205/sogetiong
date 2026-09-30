"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Button, Input, Notice, PageTitle, Select, Spinner } from "@/components/ui";
import { adminApi, useAdmin } from "@/lib/admin";
import { errorMessage } from "@/lib/api";
import { cn, dateTime, timeAgo } from "@/lib/format";

type Member = { user_id: string; subject_code: string; nickname: string | null };
type ChatRow = {
  match_id: string;
  members: [Member, Member];
  status: string;
  matched_at: string;
  ended_at: string | null;
  message_count: number;
  last_message_at: string | null;
};
type ChatList = { matches: ChatRow[]; has_more: boolean };

const MATCH_STATUS_LABEL: Record<string, string> = { ACTIVE: "대화 중", UNMATCHED: "매칭 해제", BLOCKED: "차단으로 종료" };
const PAGE = 50;

/** 매칭으로 생긴 모든 대화방 목록 (신고 여부와 상관없음). 대화 내용을 열면 감사 로그에 남는다. */
export default function ChatsPage() {
  const admin = useAdmin();
  const [items, setItems] = useState<ChatRow[] | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [error, setError] = useState("");
  const [loadingMore, setLoadingMore] = useState(false);

  const query = (offset: number) => {
    const params = new URLSearchParams({ offset: String(offset), limit: String(PAGE) });
    if (status) params.set("status", status);
    if (q.trim()) params.set("nickname", q.trim());
    return adminApi<ChatList>(`/matches?${params}`);
  };

  useEffect(() => {
    const t = setTimeout(() => {
      query(0)
        .then((r) => {
          setItems(r.matches);
          setHasMore(r.has_more);
          setError("");
        })
        .catch((e) => setError(errorMessage(e)));
    }, 250);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, q]);

  async function loadMore() {
    if (!items) return;
    setLoadingMore(true);
    try {
      const r = await query(items.length);
      setItems([...items, ...r.matches]);
      setHasMore(r.has_more);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoadingMore(false);
    }
  }

  if (!admin.can("chats:read")) return <Notice tone="error">대화 열람 권한이 없습니다.</Notice>;

  const label = (m: Member) => (
    <>
      <span className="font-mono">{m.subject_code}</span>
      <span className={m.nickname ? "" : "text-ink-faint"}> · {m.nickname ?? "(탈퇴)"}</span>
    </>
  );

  return (
    <>
      <PageTitle
        eyebrow="대화"
        title="전체 대화"
        desc="매칭으로 생긴 모든 대화방이에요. 신고가 없어도, 대화가 끝났어도 열람할 수 있어요. 대화를 열면 감사 로그에 남아요."
      />
      <div className="mb-5 grid gap-3 sm:grid-cols-[1fr_11rem]">
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="닉네임으로 찾기 (둘 중 한 명)" />
        <Select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">모든 상태</option>
          {Object.entries(MATCH_STATUS_LABEL).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </Select>
      </div>
      {error && (
        <div className="mb-4">
          <Notice tone="error">{error}</Notice>
        </div>
      )}
      {!items ? (
        !error && <Spinner />
      ) : (
        <div className="overflow-x-auto rounded-card border border-line bg-paper-card">
          <table className="w-full min-w-[44rem] text-[14px]">
            <thead className="border-b border-line text-left text-[12.5px] text-ink-faint">
              <tr>
                <th className="px-5 py-3 font-normal">참여자</th>
                <th className="px-5 py-3 font-normal">상태</th>
                <th className="px-5 py-3 text-right font-normal">메시지</th>
                <th className="px-5 py-3 font-normal">마지막 메시지</th>
                <th className="px-5 py-3 font-normal">매칭</th>
                <th className="px-5 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {items.map((c) => (
                <tr key={c.match_id} className="hover:bg-paper-deep/60">
                  <td className="px-5 py-3">
                    <div>{label(c.members[0])}</div>
                    <div>{label(c.members[1])}</div>
                  </td>
                  <td className={cn("px-5 py-3", c.status !== "ACTIVE" && "text-ink-soft")}>{MATCH_STATUS_LABEL[c.status] ?? c.status}</td>
                  <td className="num px-5 py-3 text-right">{c.message_count}</td>
                  <td className="px-5 py-3 text-ink-soft">{c.last_message_at ? timeAgo(c.last_message_at) : "—"}</td>
                  <td className="px-5 py-3 text-ink-soft">{dateTime(c.matched_at)}</td>
                  <td className="px-5 py-3 text-right">
                    <Link href={`/admin/chats/${c.match_id}`} className="whitespace-nowrap text-[13px] underline underline-offset-4">
                      대화 열기
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {items.length === 0 && <p className="py-10 text-center text-[14px] text-ink-faint">대화방이 없어요.</p>}
          {hasMore && (
            <div className="border-t border-line py-4 text-center">
              <Button size="sm" variant="secondary" loading={loadingMore} onClick={loadMore}>
                더 보기
              </Button>
            </div>
          )}
        </div>
      )}
    </>
  );
}
