"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AuthorLine } from "@/components/board/AuthorLine";
import { BoardReportModal, type BoardReportTarget } from "@/components/board/BoardReportModal";
import { ProfileSheet } from "@/components/board/ProfileSheet";
import { Button, Notice, Spinner, Textarea } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { BOARD_NAMES, type BoardComment, type BoardMe, type BoardPost } from "@/lib/board";
import { timeAgo } from "@/lib/format";

export default function PostPage() {
  const { postId } = useParams<{ postId: string }>();
  const router = useRouter();
  const [me, setMe] = useState<BoardMe | null>(null);
  const [post, setPost] = useState<BoardPost | null>(null);
  const [comments, setComments] = useState<BoardComment[]>([]);
  const [error, setError] = useState("");
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState("");
  const [sheet, setSheet] = useState<string | null>(null);
  const [report, setReport] = useState<BoardReportTarget | null>(null);

  const load = useCallback(() => {
    api<{ post: BoardPost; comments: BoardComment[] }>(`/board/posts/${postId}`)
      .then((r) => {
        setPost(r.post);
        setComments(r.comments);
      })
      .catch((e) => setError(errorMessage(e)));
  }, [postId]);

  const loadMe = useCallback(() => api<BoardMe>("/board/me").then(setMe).catch(() => {}), []);

  useEffect(() => {
    load();
    void loadMe();
  }, [load, loadMe]);

  async function addComment() {
    setSending(true);
    setSendError("");
    try {
      const c = await api<BoardComment>(`/board/posts/${postId}/comments`, { method: "POST", body: { body: text } });
      setComments((list) => [...list, c]);
      setText("");
    } catch (e) {
      setSendError(errorMessage(e));
    } finally {
      setSending(false);
    }
  }

  async function removePost() {
    if (!confirm("글을 지울까요?")) return;
    await api(`/board/posts/${postId}`, { method: "DELETE" });
    router.replace("/board");
  }

  async function removeComment(id: string) {
    if (!confirm("댓글을 지울까요?")) return;
    await api(`/board/comments/${id}`, { method: "DELETE" });
    setComments((list) => list.filter((c) => c.id !== id));
  }

  if (error)
    return (
      <div className="mx-auto max-w-app space-y-4">
        <Notice tone="error">{error}</Notice>
        <Link href="/board" className="text-[14px] underline underline-offset-4">
          게시판으로
        </Link>
      </div>
    );
  if (!post) return <Spinner />;

  const banned = Boolean(me?.profile?.banned_until);

  return (
    <div className="mx-auto max-w-app">
      <Link href="/board" className="mb-5 inline-flex items-center gap-1.5 text-[13.5px] text-ink-soft hover:text-ink">
        ← {BOARD_NAMES[post.board]} 게시판
      </Link>
      <article className="border-b border-line pb-6">
        <AuthorLine author={post.author} onClick={!post.mine && post.author.id ? () => setSheet(post.author.id) : undefined} />
        <h1 className="mt-4 font-serif text-[21px] font-semibold leading-snug">{post.title}</h1>
        <p className="mt-3 whitespace-pre-wrap break-words text-[15px] leading-relaxed text-ink">{post.body}</p>
        {post.hidden && <p className="mt-3 text-[12.5px] text-brick">신고가 쌓여 다른 사람에게 숨겨진 글이에요.</p>}
        <div className="mt-4 flex items-center gap-3 text-[12.5px] text-ink-faint">
          <span>{timeAgo(post.created_at)}</span>
          {post.mine ? (
            <button onClick={removePost} className="underline underline-offset-4">
              삭제
            </button>
          ) : (
            <button onClick={() => setReport({ type: "POST", id: post.id })} className="underline underline-offset-4">
              신고
            </button>
          )}
        </div>
      </article>

      <section className="py-5">
        <p className="eyebrow mb-3">댓글 {comments.length}</p>
        <ul className="space-y-4">
          {comments.map((c) => (
            <li key={c.id} className="space-y-1.5">
              <AuthorLine
                author={c.author}
                size={28}
                onClick={!c.mine && c.author.id ? () => setSheet(c.author.id) : undefined}
                badge={c.by_post_author ? <span className="shrink-0 rounded bg-ink px-1.5 py-0.5 text-[10.5px] text-paper">글쓴이</span> : undefined}
              />
              <p className="whitespace-pre-wrap break-words pl-[38px] text-[14.5px] leading-relaxed">{c.body}</p>
              <div className="flex items-center gap-3 pl-[38px] text-[12px] text-ink-faint">
                <span>{timeAgo(c.created_at)}</span>
                {c.mine ? (
                  <button onClick={() => removeComment(c.id)} className="underline underline-offset-4">
                    삭제
                  </button>
                ) : (
                  <button onClick={() => setReport({ type: "COMMENT", id: c.id })} className="underline underline-offset-4">
                    신고
                  </button>
                )}
                {c.hidden && <span className="text-brick">신고로 숨겨짐</span>}
              </div>
            </li>
          ))}
        </ul>

        {banned ? (
          <p className="mt-6 text-[13px] text-brick">게시판 이용 정지 중에는 댓글을 쓸 수 없어요.</p>
        ) : (
          <div className="mt-6 space-y-2">
            <Textarea value={text} rows={2} maxLength={me?.config.comment_max ?? 500} placeholder="댓글 쓰기" onChange={(e) => setText(e.target.value)} />
            {sendError && <p className="text-[13px] text-brick">{sendError}</p>}
            <Button size="sm" className="w-full" loading={sending} disabled={!text.trim()} onClick={addComment}>
              댓글 달기
            </Button>
          </div>
        )}
      </section>

      {me && (
        <ProfileSheet
          profileId={sheet}
          postId={post.id}
          me={me}
          onClose={() => setSheet(null)}
          onSpent={() => void loadMe()}
          onBlocked={() => router.replace("/board")}
        />
      )}
      <BoardReportModal target={report} onClose={() => setReport(null)} />
    </div>
  );
}
