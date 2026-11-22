"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { AuthorLine } from "@/components/board/AuthorLine";
import { BoardReportModal } from "@/components/board/BoardReportModal";
import { Button, Modal, Spinner } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import type { NoteMessage, NoteRoom } from "@/lib/board";
import { clock, cn } from "@/lib/format";
import { usePolling } from "@/lib/polling";
import { useEnterToSend } from "@/lib/enterToSend";
import { useVisualViewport } from "@/lib/viewport";

/**
 * 쪽지방 (2026-11-22). 게시판에서 시작한 대화. 매칭 대화방과 따로다.
 * 연 사람은 상대가 답장하기 전에 1개만 보낼 수 있다. 답장은 무료. 누구든 나가면 끝.
 */
export default function NoteRoomPage() {
  const { roomId } = useParams<{ roomId: string }>();
  const [room, setRoom] = useState<NoteRoom | null>(null);
  const [messages, setMessages] = useState<NoteMessage[]>([]);
  const [text, setText] = useState("");
  const [error, setError] = useState("");
  const [sending, setSending] = useState(false);
  const [panel, setPanel] = useState<"none" | "menu" | "report">("none");
  const listRef = useRef<HTMLDivElement>(null);
  const vp = useVisualViewport();
  const enterToSend = useEnterToSend(() => void send());

  const load = useCallback(
    () =>
      api<{ room: NoteRoom; messages: NoteMessage[] }>(`/notes/${roomId}`)
        .then((r) => {
          setRoom(r.room);
          setMessages((prev) => {
            if (prev.length !== r.messages.length) requestAnimationFrame(() => listRef.current?.scrollTo({ top: 1e9 }));
            return r.messages;
          });
        })
        .catch((e) => setError(errorMessage(e))),
    [roomId],
  );

  useEffect(() => {
    void load();
  }, [load]);
  usePolling(() => void load(), 5000, [load]);

  async function send(e?: React.FormEvent) {
    e?.preventDefault();
    if (!text.trim()) return;
    setSending(true);
    setError("");
    try {
      await api(`/notes/${roomId}/messages`, { method: "POST", body: { body: text } });
      setText("");
      await load();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSending(false);
    }
  }

  async function leave() {
    if (!confirm("쪽지방에서 나갈까요? 나가면 둘 다 더 보낼 수 없어요.")) return;
    await api(`/notes/${roomId}/leave`, { method: "POST" });
    setPanel("none");
    await load();
  }

  if (!room) return error ? <p className="px-5 py-16 text-center text-[14px]">{error}</p> : <Spinner />;

  const reasonText =
    room.cannot_send_reason === "WAIT_REPLY"
      ? "상대가 답장하면 이어서 쪽지를 보낼 수 있어요."
      : room.cannot_send_reason === "PARTNER_GONE"
        ? "상대가 떠난 쪽지방이에요."
        : room.cannot_send_reason === "CLOSED"
          ? "끝난 쪽지방이에요."
          : "";

  return (
    <div className={cn("fixed inset-x-0 top-0 z-40 bg-paper", !vp && "h-dvh")} style={vp ? { top: vp.top, height: vp.height } : undefined}>
      <div className="mx-auto flex h-full max-w-app flex-col px-4">
        <div className="flex shrink-0 items-center gap-3 border-b border-line py-3">
          <Link href="/matches?tab=notes" className="-ml-1 p-1 text-ink-soft hover:text-ink" aria-label="뒤로">
            <svg viewBox="0 0 10 16" className="h-4 w-2.5">
              <path d="M8.5 1.5L2 8l6.5 6.5" fill="none" stroke="currentColor" strokeWidth="1.6" />
            </svg>
          </Link>
          <div className="min-w-0 flex-1">
            <AuthorLine author={room.partner} size={34} badge={<span className="shrink-0 rounded bg-paper-deep px-1.5 py-0.5 text-[10.5px] text-ink-soft">쪽지</span>} />
          </div>
          <button onClick={() => setPanel("menu")} className="px-2 text-[13px] text-ink-soft hover:text-ink">
            더보기
          </button>
        </div>

        <div ref={listRef} className="min-h-0 flex-1 space-y-2 overflow-y-auto overscroll-contain py-5">
          <p className="pb-2 text-center text-[12px] text-ink-faint">게시판에서 시작한 쪽지예요. 소개팅 프로필은 서로 보이지 않아요.</p>
          {messages.map((m, i) => {
            const showTime = i === messages.length - 1 || messages[i + 1].mine !== m.mine;
            return (
              <div key={m.id} className={cn("flex items-end gap-2", m.mine ? "justify-end" : "justify-start")}>
                {m.mine && showTime && <span className="text-[11px] text-ink-faint">{clock(m.created_at)}</span>}
                <p
                  className={cn(
                    "max-w-[78%] whitespace-pre-wrap break-words rounded-2xl px-4 py-2.5 text-[15px] leading-relaxed",
                    m.mine ? "rounded-br-md bg-ink text-paper" : "rounded-bl-md border border-line bg-paper-card text-ink",
                  )}
                >
                  {m.body}
                </p>
                {!m.mine && showTime && <span className="text-[11px] text-ink-faint">{clock(m.created_at)}</span>}
              </div>
            );
          })}
        </div>

        {room.can_send ? (
          <form onSubmit={send} className="shrink-0 pb-[calc(max(0.5rem,env(safe-area-inset-bottom))_+_0.5rem)] pt-2">
            {error && <p className="mb-2 px-1 text-[13px] text-brick">{error}</p>}
            <div className="flex items-end gap-1.5 rounded-[24px] border border-line bg-paper-card py-1 pl-4 pr-1 focus-within:border-ink-soft">
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                // Enter = 보내기, Shift+Enter = 줄바꿈 (2026-11-22)
                {...enterToSend}
                maxLength={1000}
                rows={1}
                placeholder="쪽지 보내기"
                aria-label="쪽지"
                className="max-h-32 min-h-[40px] flex-1 resize-none bg-transparent py-2 text-[16px] leading-snug text-ink placeholder:text-ink-faint focus:outline-none sm:text-[15px]"
              />
              <button
                type="submit"
                aria-label="보내기"
                disabled={sending || !text.trim()}
                onPointerDown={(e) => e.preventDefault()}
                className="mb-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-ink text-paper transition-opacity disabled:opacity-20"
              >
                <svg viewBox="0 0 16 16" className="h-4 w-4" aria-hidden>
                  <path d="M8 13V3M3.5 7.5L8 3l4.5 4.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
            </div>
          </form>
        ) : (
          <div className="shrink-0 border-t border-line py-4 pb-[calc(max(1rem,env(safe-area-inset-bottom))_+_0.5rem)] text-center text-[14px] text-ink-soft">{reasonText}</div>
        )}
      </div>

      <Modal open={panel === "menu"} onClose={() => setPanel("none")} title="쪽지방">
        <div className="space-y-2">
          {!room.closed && (
            <Button variant="secondary" className="w-full" onClick={leave}>
              쪽지방 나가기
            </Button>
          )}
          <Button variant="danger" className="w-full" onClick={() => setPanel("report")}>
            신고하기
          </Button>
        </div>
      </Modal>
      <BoardReportModal target={panel === "report" ? { type: "NOTE", id: room.id } : null} onClose={() => setPanel("none")} />
    </div>
  );
}
