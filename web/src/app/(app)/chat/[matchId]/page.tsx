"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { Initial } from "@/components/Initial";
import { ProfileCard } from "@/components/ProfileCard";
import { ReportModal } from "@/components/ReportModal";
import { Button, Modal, Spinner } from "@/components/ui";
import { ApiError, api, errorMessage } from "@/lib/api";
import { clock, cn } from "@/lib/format";
import { usePolling } from "@/lib/polling";
import type { Card, ChatMessage } from "@/lib/types";

const POLL_MS = 4000; // MVP: 몇 초마다 새 메시지 확인 (설계도 §51)

/** 이미 있는 메시지는 빼고 합친 뒤 시간순으로 정렬 (보내기와 자동 확인이 겹쳐도 중복·순서가 꼬이지 않게) */
function mergeMessages(prev: ChatMessage[], incoming: ChatMessage[]): ChatMessage[] {
  const seen = new Set(prev.map((m) => m.message_id));
  const added = incoming.filter((m) => !seen.has(m.message_id));
  if (added.length === 0) return prev;
  return [...prev, ...added].sort((a, b) => Date.parse(a.sent_at) - Date.parse(b.sent_at));
}

export default function ChatPage() {
  const { matchId } = useParams<{ matchId: string }>();
  const router = useRouter();
  const [partner, setPartner] = useState<Card | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [text, setText] = useState("");
  const [closed, setClosed] = useState("");
  const [error, setError] = useState("");
  const [sending, setSending] = useState(false);
  const [panel, setPanel] = useState<"none" | "profile" | "menu" | "report">("none");
  const bottom = useRef<HTMLDivElement>(null);

  // 화면에 있는 마지막 메시지 ID. 몇 초마다 확인할 때 "이 뒤에 온 것만 주세요"(after)로 요청한다.
  // → 새 메시지가 없으면 서버는 빈 목록만 돌려주므로 서버·데이터 사용량이 크게 줄어든다.
  const lastIdRef = useRef<string | undefined>(undefined);
  useEffect(() => {
    lastIdRef.current = messages.at(-1)?.message_id;
  }, [messages]);

  const loadMessages = useCallback(async () => {
    try {
      const after = lastIdRef.current;
      const r = await api<{ messages: ChatMessage[] }>(
        after ? `/matches/${matchId}/messages?after=${encodeURIComponent(after)}` : `/matches/${matchId}/messages`,
      );
      if (r.messages.length === 0) return; // 새 메시지 없음 → 화면을 다시 그리지 않는다
      setMessages((prev) => mergeMessages(prev, r.messages));
    } catch (err) {
      if (err instanceof ApiError && (err.status === 403 || err.status === 404)) setClosed(err.message);
    }
  }, [matchId]);

  useEffect(() => {
    api<{ partner: Card }>(`/matches/${matchId}`)
      .then((r) => setPartner(r.partner))
      .catch((e) => setClosed(errorMessage(e)));
  }, [matchId]);

  // 새 메시지 확인: 탭이 안 보이면 멈추고, 다시 보이면 바로 확인
  usePolling(loadMessages, POLL_MS, [loadMessages]);

  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "end" });
  }, [messages.length]);

  async function send(e: React.FormEvent) {
    e.preventDefault();
    const body = text.trim();
    if (!body || sending) return;
    setSending(true);
    setError("");
    try {
      const msg = await api<ChatMessage>(`/matches/${matchId}/messages`, { method: "POST", body: { body } });
      setMessages((m) => mergeMessages(m, [msg]));
      setText("");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSending(false);
    }
  }

  async function endWith(kind: "unmatch" | "block") {
    const ok = window.confirm(kind === "block" ? "차단하면 대화가 끝나고 서로 다시 추천되지 않아요. 차단할까요?" : "매칭을 해제하면 대화가 끝나요. 해제할까요?");
    if (!ok || !partner) return;
    try {
      if (kind === "block") await api("/blocks", { method: "POST", body: { profile_id: partner.profile_id } });
      else await api(`/matches/${matchId}`, { method: "DELETE" });
      router.replace("/matches");
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  if (closed && !partner) {
    // 대화가 끝났어도(상대 탈퇴·차단·매칭 해제) 이 대화방으로 신고할 수 있다
    return (
      <div className="py-16 text-center">
        <p className="text-[15px]">{closed}</p>
        <div className="mt-5 flex items-center justify-center gap-5 text-[14px]">
          <Link href="/matches" className="underline underline-offset-4">
            대화 목록으로
          </Link>
          <button onClick={() => setPanel("report")} className="text-brick underline underline-offset-4">
            신고하기
          </button>
        </div>
        <ReportModal open={panel === "report"} onClose={() => setPanel("none")} matchId={matchId} />
      </div>
    );
  }
  if (!partner) return <Spinner />;

  return (
    <div className="mx-auto flex h-[calc(100dvh-3.5rem)] max-w-app flex-col">
      <div className="flex items-center gap-3 border-b border-line py-3">
        <Link href="/matches" className="-ml-1 p-1 text-ink-soft hover:text-ink" aria-label="뒤로">
          <svg viewBox="0 0 10 16" className="h-4 w-2.5">
            <path d="M8.5 1.5L2 8l6.5 6.5" fill="none" stroke="currentColor" strokeWidth="1.6" />
          </svg>
        </Link>
        <button onClick={() => setPanel("profile")} className="flex min-w-0 flex-1 items-center gap-3 text-left">
          <Initial name={partner.nickname} size={36} />
          <span className="min-w-0">
            <span className="block truncate text-[15px] font-semibold">{partner.nickname}</span>
            <span className="block text-[12px] text-ink-faint">프로필 보기</span>
          </span>
        </button>
        <button onClick={() => setPanel("menu")} className="px-2 text-[13px] text-ink-soft hover:text-ink">
          더보기
        </button>
      </div>

      <div className="flex-1 space-y-2 overflow-y-auto py-5">
        {messages.length === 0 && (
          <div className="py-10 text-center text-[13.5px] leading-relaxed text-ink-faint">
            서로의 프로필에서 공통점을 찾아 먼저 인사해보세요.
            <br />
            연락처나 SNS는 충분히 신뢰가 쌓인 뒤에 나눠도 늦지 않아요.
          </div>
        )}
        {messages.map((m, i) => {
          const showTime = i === messages.length - 1 || messages[i + 1].is_mine !== m.is_mine;
          return (
            <div key={m.message_id} className={cn("flex items-end gap-2", m.is_mine ? "justify-end" : "justify-start")}>
              {m.is_mine && showTime && <span className="text-[11px] text-ink-faint">{clock(m.sent_at)}</span>}
              <p
                className={cn(
                  "max-w-[78%] whitespace-pre-wrap break-words rounded-2xl px-4 py-2.5 text-[15px] leading-relaxed",
                  m.is_mine ? "rounded-br-md bg-ink text-paper" : "rounded-bl-md border border-line bg-paper-card text-ink",
                )}
              >
                {m.body}
              </p>
              {!m.is_mine && showTime && <span className="text-[11px] text-ink-faint">{clock(m.sent_at)}</span>}
            </div>
          );
        })}
        <div ref={bottom} />
      </div>

      {closed ? (
        <div className="border-t border-line py-4 text-center text-[14px] text-ink-soft">
          {closed}{" "}
          <button onClick={() => setPanel("report")} className="ml-2 text-brick underline underline-offset-4">
            신고하기
          </button>
        </div>
      ) : (
        <form onSubmit={send} className="border-t border-line py-3">
          {error && <p className="mb-2 text-[13px] text-brick">{error}</p>}
          <div className="flex items-end gap-2">
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                  e.preventDefault();
                  send(e);
                }
              }}
              maxLength={1000}
              rows={1}
              placeholder="메시지 보내기"
              className="field max-h-32 min-h-[46px] flex-1 resize-none py-3"
            />
            <Button type="submit" className="h-[46px]" disabled={!text.trim()} loading={sending}>
              보내기
            </Button>
          </div>
        </form>
      )}

      <Modal open={panel === "profile"} onClose={() => setPanel("none")} title="상대 프로필">
        <div className="max-h-[70vh] overflow-y-auto">
          <ProfileCard card={partner} />
        </div>
      </Modal>

      <Modal open={panel === "menu"} onClose={() => setPanel("none")} title="대화 관리">
        <div className="space-y-2">
          <Button variant="secondary" className="w-full" onClick={() => endWith("unmatch")}>
            매칭 해제
          </Button>
          <Button variant="secondary" className="w-full" onClick={() => endWith("block")}>
            차단하기
          </Button>
          <Button variant="danger" className="w-full" onClick={() => setPanel("report")}>
            신고하기
          </Button>
          <p className="pt-2 text-center text-[12.5px] text-ink-faint">상대에게는 차단·신고 사실이 알려지지 않아요.</p>
        </div>
      </Modal>

      <ReportModal open={panel === "report"} onClose={() => setPanel("none")} matchId={matchId} />
    </div>
  );
}
