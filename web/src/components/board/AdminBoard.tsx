"use client";

import Link from "next/link";
import { useState } from "react";
import { GenderMark } from "@/components/board/AuthorLine";
import { Button, Input, Notice } from "@/components/ui";
import { adminApi, useAdmin } from "@/lib/admin";
import { errorMessage } from "@/lib/api";
import { BOARD_NAMES, type BoardAuthor, type BoardKey } from "@/lib/board";
import { dateTime, shortSchoolName } from "@/lib/format";

export type AdminBoardPerson = BoardAuthor & {
  user_id: string;
  dating_nickname: string | null;
  banned_until: string | null;
  ban_permanent: boolean;
  ban_reason: string | null;
};

export type AdminPost = {
  id: string;
  board: BoardKey;
  title: string;
  body: string;
  author: BoardAuthor;
  author_user_id: string;
  comment_count: number;
  hidden: boolean;
  deleted: boolean;
  created_at: string;
};

export type AdminComment = {
  id: string;
  post_id: string;
  body: string;
  author: BoardAuthor;
  author_user_id: string;
  hidden: boolean;
  deleted: boolean;
  created_at: string;
};

/** 관리자 화면용 게시판 사람 한 줄 (게시판 닉네임 + 소개팅 닉네임 + 정지 상태) */
export function PersonLine({ person }: { person: AdminBoardPerson }) {
  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[13.5px]">
      {person.id ? (
        <Link href={`/admin/board/profiles/${person.id}`} className="font-semibold underline underline-offset-4">
          {person.nickname}
        </Link>
      ) : (
        <span className="text-ink-faint">{person.nickname}</span>
      )}
      {person.gender && <GenderMark gender={person.gender} />}
      {person.school && <span className="text-ink-faint">{shortSchoolName(person.school)}</span>}
      {person.dating_nickname && <span className="text-ink-faint">(소개팅: {person.dating_nickname})</span>}
      <Link href={`/admin/users/${person.user_id}`} className="text-[12px] text-ink-faint underline underline-offset-4">
        사용자 화면
      </Link>
      {person.banned_until && (
        <span className="rounded bg-brick-wash px-1.5 py-0.5 text-[11.5px] font-semibold text-brick">
          게시판 정지 {person.ban_permanent ? "영구" : `~${dateTime(person.banned_until)}`}
        </span>
      )}
    </div>
  );
}

const BAN_OPTIONS: { days: number | null; label: string }[] = [
  { days: 1, label: "1일" },
  { days: 7, label: "7일" },
  { days: 30, label: "30일" },
  { days: null, label: "영구" },
];

/** 게시판 이용 정지·해제. 정지하면 사용자에게 앱 알림 + 휴대폰 알림(안 되면 메일)이 간다. */
export function BanBox({ person, onChanged, defaultReason = "" }: { person: AdminBoardPerson; onChanged: () => void; defaultReason?: string }) {
  const { can } = useAdmin();
  const [days, setDays] = useState<number | null>(7);
  const [reason, setReason] = useState(defaultReason);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  if (!person.id || !can("users:status")) return null;

  async function run(path: "ban" | "unban") {
    setLoading(true);
    setError("");
    try {
      await adminApi(`/board/profiles/${person.id}/${path}`, { method: "POST", body: path === "ban" ? { days, reason } : undefined });
      onChanged();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-2 rounded-md border border-line bg-paper-deep p-3">
      {person.banned_until ? (
        <>
          <p className="text-[13px] text-brick">정지 사유: {person.ban_reason}</p>
          <Button size="sm" variant="secondary" loading={loading} onClick={() => run("unban")}>
            정지 풀기 (사용자에게 알림)
          </Button>
        </>
      ) : (
        <>
          <p className="text-[12.5px] font-medium text-ink-soft">게시판 이용 정지 (글·댓글·쪽지 보내기 금지, 소개팅은 그대로)</p>
          <div className="flex flex-wrap gap-1.5">
            {BAN_OPTIONS.map((o) => (
              <button
                key={o.label}
                type="button"
                onClick={() => setDays(o.days)}
                className={days === o.days ? "rounded-md bg-ink px-3 py-1.5 text-[13px] text-paper" : "rounded-md border border-line bg-paper-card px-3 py-1.5 text-[13px]"}
              >
                {o.label}
              </button>
            ))}
          </div>
          <div className="flex flex-wrap gap-1.5">
            {["자유·연애 게시판에서 성적인 이야기", "욕설·비하", "개인정보 노출", "광고·도배"].map((r) => (
              <button key={r} type="button" onClick={() => setReason(r)} className="rounded-full border border-line px-2.5 py-1 text-[12px] text-ink-soft hover:border-ink">
                {r}
              </button>
            ))}
          </div>
          <Input value={reason} maxLength={300} placeholder="사유 (사용자에게 보여요)" onChange={(e) => setReason(e.target.value)} />
          <Button size="sm" variant="danger" loading={loading} disabled={!reason.trim()} onClick={() => run("ban")}>
            정지하고 알림 보내기
          </Button>
        </>
      )}
      {error && <Notice tone="error">{error}</Notice>}
    </div>
  );
}

export function BoardBadge({ board }: { board: BoardKey | null | undefined }) {
  if (!board) return null;
  return <span className="rounded bg-paper-deep px-1.5 py-0.5 text-[11.5px] text-ink-soft">{BOARD_NAMES[board]}</span>;
}

/** 글·댓글 즉시 삭제 / 숨김 풀기 버튼 */
export function ContentActions({ kind, id, hidden, deleted, onChanged }: { kind: "posts" | "comments"; id: string; hidden: boolean; deleted: boolean; onChanged: () => void }) {
  const { can } = useAdmin();
  const [loading, setLoading] = useState(false);
  if (!can("reports:update")) return null;
  if (deleted) return <span className="text-[12.5px] text-ink-faint">삭제됨</span>;

  async function act(method: "DELETE" | "POST", path: string, ask?: string) {
    if (ask && !confirm(ask)) return;
    setLoading(true);
    try {
      await adminApi(path, { method });
      onChanged();
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex gap-2">
      <Button size="sm" variant="danger" loading={loading} onClick={() => act("DELETE", `/board/${kind}/${id}`, "바로 지울까요? 모두에게서 사라져요.")}>
        즉시 삭제
      </Button>
      {hidden && (
        <Button size="sm" variant="secondary" loading={loading} onClick={() => act("POST", `/board/${kind}/${id}/unhide`)}>
          숨김 풀기
        </Button>
      )}
    </div>
  );
}

export type AdminNoteRoom = {
  id: string;
  starter: BoardAuthor;
  receiver: BoardAuthor;
  messages: number;
  paid_with: "SUPER_LIKE" | "FREE";
  closed: boolean;
  reported: boolean;
  last_message_at: string;
  created_at: string;
};

/** 쪽지방 목록 (내용은 안 보임). 누르면 내용 화면 — 열 때마다 열람 기록이 남는다 */
export function NoteRoomList({ rooms }: { rooms: AdminNoteRoom[] }) {
  const { can } = useAdmin();
  if (rooms.length === 0) return <p className="py-8 text-center text-[14px] text-ink-faint">쪽지방이 없어요.</p>;
  return (
    <ul className="divide-y divide-line rounded-card border border-line bg-paper-card">
      {rooms.map((r) => {
        const row = (
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1 px-4 py-3 text-[13.5px]">
            <span className="font-semibold">{r.starter.nickname}</span>
            <span className="text-ink-faint">→</span>
            <span className="font-semibold">{r.receiver.nickname}</span>
            <span className="text-[12px] text-ink-faint">
              쪽지 {r.messages}개 · {r.paid_with === "FREE" ? "무료" : "슈퍼 라이크"} · {dateTime(r.last_message_at)}
            </span>
            {r.closed && <span className="rounded bg-paper-deep px-1.5 py-0.5 text-[11.5px] text-ink-soft">끝남</span>}
            {r.reported && <span className="rounded bg-brick-wash px-1.5 py-0.5 text-[11.5px] font-semibold text-brick">신고됨</span>}
            {can("chats:read") && <span className="ml-auto text-[12px] text-ink-faint underline underline-offset-4">내용 보기</span>}
          </div>
        );
        return (
          <li key={r.id}>
            {can("chats:read") ? (
              <Link href={`/admin/board/notes/${r.id}`} className="block hover:bg-paper-deep/60">
                {row}
              </Link>
            ) : (
              row
            )}
          </li>
        );
      })}
    </ul>
  );
}
