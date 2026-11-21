"use client";

/* eslint-disable @next/next/no-img-element */
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { type AdminBoardPerson, type AdminComment, type AdminPost, BanBox, BoardBadge, ContentActions, PersonLine } from "@/components/board/AdminBoard";
import { Button, PageTitle, Spinner } from "@/components/ui";
import { adminApi, useAdmin } from "@/lib/admin";
import { dateTime } from "@/lib/format";

type Activity = {
  profile: AdminBoardPerson;
  posts: AdminPost[];
  comments: AdminComment[];
  reports: { id: string; target_type: string; reason_label: string; status: string; created_at: string }[];
};

/** 관리자: 한 사람의 게시판 활동 (프로필, 글, 댓글, 받은 신고) + 정지 */
export default function AdminBoardProfilePage() {
  const { profileId } = useParams<{ profileId: string }>();
  const { can } = useAdmin();
  const [data, setData] = useState<Activity | null>(null);
  const load = useCallback(() => {
    adminApi<Activity>(`/board/profiles/${profileId}`).then(setData);
  }, [profileId]);
  useEffect(load, [load]);
  if (!data) return <Spinner />;
  const p = data.profile;

  async function resetAvatar() {
    if (!confirm("프사를 지울까요?")) return;
    await adminApi(`/board/profiles/${profileId}/reset-avatar`, { method: "POST" });
    load();
  }

  return (
    <>
      <Link href="/admin/board" className="mb-4 inline-block text-[13.5px] text-ink-soft">
        ← 게시판 관리
      </Link>
      <PageTitle eyebrow="게시판 활동" title={p.nickname} />
      <div className="space-y-4">
        <div className="flex items-center gap-4">
          {p.has_avatar ? (
            <img src={`/api/v1/admin/board/avatars/${profileId}`} alt="" className="h-16 w-16 rounded-full border border-line object-cover" />
          ) : (
            <span className="text-[13px] text-ink-faint">프사 없음 (기본 그림)</span>
          )}
          {p.has_avatar && can("reports:update") && (
            <Button size="sm" variant="danger" onClick={resetAvatar}>
              프사 지우기
            </Button>
          )}
        </div>
        <PersonLine person={p} />
        <BanBox person={p} onChanged={load} />
      </div>

      <p className="eyebrow mb-3 mt-8">받은 신고 {data.reports.length}</p>
      <ul className="space-y-1 text-[13px]">
        {data.reports.map((r) => (
          <li key={r.id} className="text-ink-soft">
            {dateTime(r.created_at)} · {r.target_type} · {r.reason_label} · {r.status}
          </li>
        ))}
      </ul>

      <p className="eyebrow mb-3 mt-8">글 {data.posts.length}</p>
      <div className="space-y-2">
        {data.posts.map((x) => (
          <div key={x.id} className="space-y-2 rounded-md border border-line bg-paper-card p-3">
            <div className="flex items-center gap-2 text-[12.5px] text-ink-faint">
              <BoardBadge board={x.board} /> {dateTime(x.created_at)} {x.hidden && <span className="text-brick">숨김</span>}
            </div>
            <Link href={`/admin/board/posts/${x.id}`} className="block">
              <p className="font-semibold">{x.title}</p>
              <p className="line-clamp-3 whitespace-pre-wrap text-[13.5px] text-ink-soft">{x.body}</p>
            </Link>
            <ContentActions kind="posts" id={x.id} hidden={x.hidden} deleted={x.deleted} onChanged={load} />
          </div>
        ))}
      </div>

      <p className="eyebrow mb-3 mt-8">댓글 {data.comments.length}</p>
      <div className="space-y-2">
        {data.comments.map((c) => (
          <div key={c.id} className="space-y-2 rounded-md border border-line bg-paper-card p-3">
            <p className="text-[12.5px] text-ink-faint">
              {dateTime(c.created_at)} ·{" "}
              <Link href={`/admin/board/posts/${c.post_id}`} className="underline underline-offset-4">
                글 보기
              </Link>
              {c.hidden && <span className="ml-2 text-brick">숨김</span>}
            </p>
            <p className="whitespace-pre-wrap text-[14px]">{c.body}</p>
            <ContentActions kind="comments" id={c.id} hidden={c.hidden} deleted={c.deleted} onChanged={load} />
          </div>
        ))}
      </div>
    </>
  );
}
