"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { type AdminComment, type AdminPost, BoardBadge, ContentActions } from "@/components/board/AdminBoard";
import { PageTitle, Spinner } from "@/components/ui";
import { adminApi } from "@/lib/admin";
import { dateTime } from "@/lib/format";

/** 관리자: 글 전체 + 모든 댓글 (숨김·삭제 포함) */
export default function AdminPostPage() {
  const { postId } = useParams<{ postId: string }>();
  const [data, setData] = useState<{ post: AdminPost; comments: AdminComment[] } | null>(null);
  const load = useCallback(() => {
    adminApi<{ post: AdminPost; comments: AdminComment[] }>(`/board/posts/${postId}`).then(setData);
  }, [postId]);
  useEffect(load, [load]);
  if (!data) return <Spinner />;
  const { post, comments } = data;

  return (
    <>
      <Link href="/admin/board" className="mb-4 inline-block text-[13.5px] text-ink-soft">
        ← 게시판 관리
      </Link>
      <PageTitle eyebrow="게시판 글" title={post.title} />
      <div className="space-y-3 rounded-card border border-line bg-paper-card p-4">
        <div className="flex items-center gap-2 text-[12.5px] text-ink-faint">
          <BoardBadge board={post.board} />
          <Who id={post.author.id} name={post.author.nickname} />
          <span>· {dateTime(post.created_at)}</span>
          {post.hidden && <span className="text-brick">자동 숨김</span>}
        </div>
        <p className="whitespace-pre-wrap break-words text-[14.5px]">{post.body}</p>
        <ContentActions kind="posts" id={post.id} hidden={post.hidden} deleted={post.deleted} onChanged={load} />
      </div>
      <p className="eyebrow mb-3 mt-8">댓글 {comments.length}</p>
      <div className="space-y-2">
        {comments.map((c) => (
          <div key={c.id} className="space-y-2 rounded-md border border-line bg-paper-card p-3">
            <div className="flex items-center gap-2 text-[12.5px] text-ink-faint">
              <Who id={c.author.id} name={c.author.nickname} />
              <span>· {dateTime(c.created_at)}</span>
              {c.hidden && <span className="text-brick">자동 숨김</span>}
            </div>
            <p className="whitespace-pre-wrap break-words text-[14px]">{c.body}</p>
            <ContentActions kind="comments" id={c.id} hidden={c.hidden} deleted={c.deleted} onChanged={load} />
          </div>
        ))}
      </div>
    </>
  );
}

function Who({ id, name }: { id: string | null; name: string }) {
  return id ? (
    <Link href={`/admin/board/profiles/${id}`} className="font-semibold text-ink underline underline-offset-4">
      {name}
    </Link>
  ) : (
    <span>{name}</span>
  );
}
