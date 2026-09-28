"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { Initial } from "@/components/Initial";
import { ProfileCard } from "@/components/ProfileCard";
import { Button, Field, Modal, Notice, Spinner, Textarea } from "@/components/ui";
import { ApiError, api, errorMessage } from "@/lib/api";
import { clock, cn } from "@/lib/format";
import { usePolling } from "@/lib/polling";
import { REPORT_REASONS, type Card, type ChatMessage } from "@/lib/types";

const POLL_MS = 4000; // MVP: 몇 초마다 새 메시지 확인 (설계도 §51)

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

  const loadMessages = useCallback(async () => {
    try {
      const r = await api<{ messages: ChatMessage[] }>(`/matches/${matchId}/messages`);
      setMessages((prev) => (prev.length === r.messages.length && prev.at(-1)?.message_id === r.messages.at(-1)?.message_id ? prev : r.messages));
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
      setMessages((m) => [...m, msg]);
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
    return (
      <div className="py-16 text-center">
        <p className="text-[15px]">{closed}</p>
        <Link href="/matches" className="mt-4 inline-block text-[14px] underline underline-offset-4">
          대화 목록으로
        </Link>
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
        <div className="border-t border-line py-4 text-center text-[14px] text-ink-soft">{closed}</div>
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

      <ReportModal open={panel === "report"} onClose={() => setPanel("none")} profileId={partner.profile_id} matchId={matchId} />
    </div>
  );
}

function ReportModal({ open, onClose, profileId, matchId }: { open: boolean; onClose: () => void; profileId: string; matchId: string }) {
  const [reason, setReason] = useState("");
  const [desc, setDesc] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit() {
    setLoading(true);
    setError("");
    try {
      await api("/reports", { method: "POST", body: { profile_id: profileId, reason, description: desc || null, match_id: matchId } });
      setDone(true);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="신고하기">
      {done ? (
        <div className="space-y-4">
          <Notice tone="ok">신고가 접수됐어요. 운영진이 확인한 뒤 알림으로 결과를 알려드릴게요.</Notice>
          <Button variant="secondary" className="w-full" onClick={onClose}>
            닫기
          </Button>
        </div>
      ) : (
        <div className="space-y-5">
          <div className="grid grid-cols-2 gap-2">
            {REPORT_REASONS.map((r) => (
              <button
                key={r.value}
                type="button"
                onClick={() => setReason(r.value)}
                className={cn("rounded-md border px-3 py-2.5 text-left text-[14px]", reason === r.value ? "border-ink bg-ink text-paper" : "border-line bg-paper-card hover:border-line-strong")}
              >
                {r.label}
              </button>
            ))}
          </div>
          <Field label="자세한 내용 (선택)">
            <Textarea value={desc} maxLength={1000} onChange={(e) => setDesc(e.target.value)} rows={3} />
          </Field>
          {error && <Notice tone="error">{error}</Notice>}
          <Button variant="danger" className="w-full" disabled={!reason} loading={loading} onClick={submit}>
            신고 접수
          </Button>
        </div>
      )}
    </Modal>
  );
}
