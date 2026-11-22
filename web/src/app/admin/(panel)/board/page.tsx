"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { type AdminBoardPerson, type AdminPost, BanBox, BoardBadge, ContentActions, NoteRoomList, type AdminNoteRoom, PersonLine } from "@/components/board/AdminBoard";
import { Button, PageTitle, Spinner } from "@/components/ui";
import { adminApi, useAdmin } from "@/lib/admin";
import { BOARD_NAMES, type BoardKey } from "@/lib/board";
import { dateTime } from "@/lib/format";

type Report = {
  id: string;
  target_type: "POST" | "COMMENT" | "PROFILE" | "NOTE";
  target_id: string;
  reason: string;
  reason_label: string;
  description: string | null;
  status: string;
  created_at: string;
  reports_on_target: number;
  reported: AdminBoardPerson;
  target: { board?: BoardKey | null; title?: string; text?: string; hidden?: boolean; deleted?: boolean; post_id?: string; has_avatar?: boolean; note_room_id?: string };
};

const TARGET_LABEL = { POST: "글", COMMENT: "댓글", PROFILE: "프로필", NOTE: "쪽지" };

/** 게시판 관리 (2026-11-22): 신고 처리 · 최근 글 즉시 삭제 · 이용 정지 */
export default function AdminBoardPage() {
  const [tab, setTab] = useState<"reports" | "posts" | "notes">("reports");
  return (
    <>
      <PageTitle eyebrow="게시판" title="게시판 관리" desc="신고 3번이면 자동으로 숨겨져요. 신고가 없어도 최근 글에서 바로 지울 수 있어요. 자유·연애 게시판의 성적인 이야기는 정지 사유예요." />
      <div className="mb-6 flex gap-6 border-b border-line text-[14px]">
        {(["reports", "posts", "notes"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)} className={tab === t ? "-mb-px border-b-2 border-ink pb-3 font-semibold" : "pb-3 text-ink-faint hover:text-ink"}>
            {t === "reports" ? "신고" : t === "posts" ? "최근 글" : "쪽지"}
          </button>
        ))}
      </div>
      {tab === "reports" ? <Reports /> : tab === "posts" ? <RecentPosts /> : <NoteRooms />}
    </>
  );
}

function Reports() {
  const [status, setStatus] = useState("OPEN");
  const [items, setItems] = useState<Report[] | null>(null);
  const load = useCallback(() => {
    adminApi<{ reports: Report[] }>(`/board/reports?status=${status}`).then((r) => setItems(r.reports));
  }, [status]);
  useEffect(() => {
    setItems(null);
    load();
  }, [load]);

  return (
    <>
      <div className="mb-4 flex gap-2">
        {[
          ["OPEN", "처리 전"],
          ["RESOLVED", "처리함"],
          ["DISMISSED", "기각"],
        ].map(([v, l]) => (
          <button key={v} onClick={() => setStatus(v)} className={status === v ? "rounded-full bg-ink px-3 py-1 text-[13px] text-paper" : "rounded-full border border-line px-3 py-1 text-[13px]"}>
            {l}
          </button>
        ))}
      </div>
      {!items ? (
        <Spinner />
      ) : items.length === 0 ? (
        <p className="py-12 text-center text-[14px] text-ink-faint">신고가 없어요.</p>
      ) : (
        <div className="space-y-3">
          {items.map((r) => (
            <ReportRow key={r.id} report={r} onChanged={load} />
          ))}
        </div>
      )}
    </>
  );
}

function ReportRow({ report: r, onChanged }: { report: Report; onChanged: () => void }) {
  const { can } = useAdmin();
  async function resolve(status: "RESOLVED" | "DISMISSED") {
    await adminApi(`/board/reports/${r.id}`, { method: "POST", body: { status } });
    onChanged();
  }
  async function resetAvatar() {
    if (!confirm("이 사람의 프사를 지울까요?")) return;
    await adminApi(`/board/profiles/${r.reported.id}/reset-avatar`, { method: "POST" });
    onChanged();
  }

  return (
    <div className="space-y-3 rounded-card border border-line bg-paper-card p-4">
      <div className="flex flex-wrap items-center gap-2 text-[13px]">
        <span className="rounded bg-brick-wash px-1.5 py-0.5 font-semibold text-brick">{r.reason_label}</span>
        <span className="font-semibold">{TARGET_LABEL[r.target_type]}</span>
        <BoardBadge board={r.target.board} />
        <span className="text-ink-faint">이 대상 신고 {r.reports_on_target}건</span>
        <span className="ml-auto text-[12px] text-ink-faint">{dateTime(r.created_at)}</span>
      </div>
      <PersonLine person={r.reported} />
      {(r.target.title || r.target.text) && (
        <div className="rounded-md border border-line bg-paper px-3 py-2 text-[13.5px]">
          {r.target.title && <p className="font-semibold">{r.target.title}</p>}
          {r.target.text && <p className="whitespace-pre-wrap break-words text-ink-soft">{r.target.text}</p>}
          <p className="mt-1 text-[12px] text-ink-faint">
            {r.target.deleted ? "삭제됨" : r.target.hidden ? "자동 숨김 중" : "보이는 중"}
            {r.target.post_id && (
              <>
                {" · "}
                <Link href={`/admin/board/posts/${r.target.post_id}`} className="underline underline-offset-4">
                  글 전체 보기
                </Link>
              </>
            )}
          </p>
        </div>
      )}
      {r.description && <p className="text-[13px] text-ink-soft">신고 내용: {r.description}</p>}
      <div className="flex flex-wrap gap-2">
        {(r.target_type === "POST" || r.target_type === "COMMENT") && (
          <ContentActions kind={r.target_type === "POST" ? "posts" : "comments"} id={r.target_id} hidden={Boolean(r.target.hidden)} deleted={Boolean(r.target.deleted)} onChanged={onChanged} />
        )}
        {r.target_type === "PROFILE" && r.target.has_avatar && can("reports:update") && (
          <Button size="sm" variant="danger" onClick={resetAvatar}>
            프사 지우기
          </Button>
        )}
        {r.target_type === "NOTE" && can("chats:read") && (
          <Link href={`/admin/board/notes/${r.target_id}`} className="inline-flex h-9 items-center rounded-md border border-line-strong px-3.5 text-[13px]">
            쪽지 내용 보기 (기록됨)
          </Link>
        )}
      </div>
      <BanBox person={r.reported} onChanged={onChanged} defaultReason={r.reason === "SEXUAL" ? "자유·연애 게시판에서 성적인 이야기" : ""} />
      {r.status === "OPEN" && can("reports:update") && (
        <div className="flex gap-2 border-t border-line pt-3">
          <Button size="sm" onClick={() => resolve("RESOLVED")}>
            처리 완료
          </Button>
          <Button size="sm" variant="secondary" onClick={() => resolve("DISMISSED")}>
            문제없음 (기각)
          </Button>
        </div>
      )}
    </div>
  );
}

function RecentPosts() {
  const [board, setBoard] = useState<BoardKey | "ALL">("ALL");
  const [posts, setPosts] = useState<AdminPost[] | null>(null);
  const load = useCallback(() => {
    adminApi<{ posts: AdminPost[] }>(`/board/posts${board === "ALL" ? "" : `?board=${board}`}`).then((r) => setPosts(r.posts));
  }, [board]);
  useEffect(() => {
    setPosts(null);
    load();
  }, [load]);

  return (
    <>
      <div className="mb-4 flex gap-2">
        {(["ALL", "FREE", "LOVE", "CASUAL"] as const).map((b) => (
          <button key={b} onClick={() => setBoard(b)} className={board === b ? "rounded-full bg-ink px-3 py-1 text-[13px] text-paper" : "rounded-full border border-line px-3 py-1 text-[13px]"}>
            {b === "ALL" ? "전체" : BOARD_NAMES[b]}
          </button>
        ))}
      </div>
      {!posts ? (
        <Spinner />
      ) : posts.length === 0 ? (
        <p className="py-12 text-center text-[14px] text-ink-faint">글이 없어요.</p>
      ) : (
        <div className="space-y-3">
          {posts.map((p) => (
            <div key={p.id} className="space-y-2 rounded-card border border-line bg-paper-card p-4">
              <div className="flex items-center gap-2 text-[12.5px] text-ink-faint">
                <BoardBadge board={p.board} />
                <span>{p.author.nickname}</span>
                <span>· {dateTime(p.created_at)}</span>
                <span>· 댓글 {p.comment_count}</span>
                {p.hidden && <span className="text-brick">자동 숨김</span>}
              </div>
              <Link href={`/admin/board/posts/${p.id}`} className="block">
                <p className="font-semibold">{p.title}</p>
                <p className="line-clamp-3 whitespace-pre-wrap text-[13.5px] text-ink-soft">{p.body}</p>
              </Link>
              <ContentActions kind="posts" id={p.id} hidden={p.hidden} deleted={p.deleted} onChanged={load} />
            </div>
          ))}
        </div>
      )}
    </>
  );
}

/** 최근 쪽지방 (2026-11-22). 신고가 없어도 관리자가 열어 볼 수 있다 (열면 기록이 남음) */
function NoteRooms() {
  const { can } = useAdmin();
  const [rooms, setRooms] = useState<AdminNoteRoom[] | null>(null);
  useEffect(() => {
    if (!can("chats:read")) return;
    adminApi<{ rooms: AdminNoteRoom[] }>("/board/notes").then((r) => setRooms(r.rooms));
  }, [can]);
  if (!can("chats:read")) return <p className="py-12 text-center text-[14px] text-ink-faint">쪽지를 볼 권한이 없어요.</p>;
  if (!rooms) return <Spinner />;
  return <NoteRoomList rooms={rooms} />;
}
