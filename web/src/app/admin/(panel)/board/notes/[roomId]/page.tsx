"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Notice, PageTitle, Spinner } from "@/components/ui";
import { adminApi } from "@/lib/admin";
import { errorMessage } from "@/lib/api";
import type { BoardAuthor } from "@/lib/board";
import { cn, dateTime } from "@/lib/format";

type Room = {
  starter: BoardAuthor;
  receiver: BoardAuthor;
  closed: boolean;
  messages: { from: "STARTER" | "RECEIVER"; body: string; created_at: string }[];
};

/** 관리자: 신고된 쪽지방 내용 (열 때마다 감사 로그 NOTE_VIEW) */
export default function AdminNotePage() {
  const { roomId } = useParams<{ roomId: string }>();
  const [room, setRoom] = useState<Room | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    adminApi<Room>(`/board/notes/${roomId}`)
      .then(setRoom)
      .catch((e) => setError(errorMessage(e)));
  }, [roomId]);
  if (error) return <Notice tone="error">{error}</Notice>;
  if (!room) return <Spinner />;
  return (
    <>
      <Link href="/admin/board" className="mb-4 inline-block text-[13.5px] text-ink-soft">
        ← 게시판 관리
      </Link>
      <PageTitle eyebrow="쪽지 (열람 기록이 남아요)" title={`${room.starter.nickname} → ${room.receiver.nickname}`} desc={room.closed ? "끝난 쪽지방" : undefined} />
      <div className="space-y-2">
        {room.messages.map((m, i) => (
          <div key={i} className={cn("flex", m.from === "STARTER" ? "justify-start" : "justify-end")}>
            <div className={cn("max-w-[78%] rounded-2xl px-4 py-2.5 text-[14.5px]", m.from === "STARTER" ? "border border-line bg-paper-card" : "bg-ink text-paper")}>
              <p className="text-[11px] opacity-70">
                {m.from === "STARTER" ? room.starter.nickname : room.receiver.nickname} · {dateTime(m.created_at)}
              </p>
              <p className="whitespace-pre-wrap break-words">{m.body}</p>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
