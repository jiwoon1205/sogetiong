"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { AuthorLine } from "@/components/board/AuthorLine";
import { BoardReportModal, type BoardReportTarget } from "@/components/board/BoardReportModal";
import { ProfileSheet } from "@/components/board/ProfileSheet";
import { Notice, Spinner } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { useEnterToSend } from "@/lib/enterToSend";
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
  // 답글 쓰는 중인 댓글 (2026-11-22)
  const [replyTo, setReplyTo] = useState<BoardComment | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  // Enter = 댓글 등록, Shift+Enter = 줄바꿈 (2026-11-22)
  const enterToSend = useEnterToSend(() => {
    if (text.trim() && !sending) void addComment();
  });

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
      const c = await api<BoardComment>(`/board/posts/${postId}/comments`, {
        method: "POST",
        body: { body: text, reply_to_id: replyTo?.id ?? null },
      });
      setComments((list) => [...list, c]);
      setText("");
      if (inputRef.current) inputRef.current.style.height = "auto";
      if (replyTo) {
        setReplyTo(null);
        // 방금 단 답글이 보이게
        requestAnimationFrame(() => document.getElementById(`c-${c.id}`)?.scrollIntoView({ behavior: "smooth", block: "center" }));
      } else {
        requestAnimationFrame(() => window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" }));
      }
    } catch (e) {
      setSendError(errorMessage(e));
    } finally {
      setSending(false);
    }
  }

  function startReply(c: BoardComment) {
    setReplyTo(c);
    setSendError("");
    inputRef.current?.focus();
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
          {threads(comments).map(({ root, rootId, replies }) => (
            <li key={rootId} className="space-y-3">
              {root ? (
                <CommentItem
                  c={root}
                  onAuthor={setSheet}
                  onReply={banned ? undefined : startReply}
                  onDelete={removeComment}
                  onReport={(id) => setReport({ type: "COMMENT", id })}
                />
              ) : (
                <p className="text-[13.5px] text-ink-faint">삭제된 댓글이에요.</p>
              )}
              {replies.length > 0 && (
                <ul className="space-y-3 border-l-2 border-line pl-4">
                  {replies.map((r) => (
                    <li key={r.id}>
                      <CommentItem
                        c={r}
                        small
                        onAuthor={setSheet}
                        onReply={banned ? undefined : startReply}
                        onDelete={removeComment}
                        onReport={(id) => setReport({ type: "COMMENT", id })}
                      />
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>

        {banned && <p className="mt-6 text-[13px] text-brick">게시판 이용 정지 중에는 댓글을 쓸 수 없어요.</p>}
        {/* 아래에 떠 있는 댓글 칸에 마지막 댓글이 가리지 않게 */}
        {!banned && <div className="h-20" aria-hidden />}
      </section>

      {/* 댓글 쓰기 (2026-11-22): 채팅 입력창처럼 화면 아래에 한 줄로 붙어 있다. 휴대폰은 아래 탭 바로 위 */}
      {!banned && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (text.trim() && !sending) void addComment();
          }}
          className="fixed inset-x-0 bottom-[calc(4.5rem_+_env(safe-area-inset-bottom))] z-20 border-t border-line bg-paper px-4 py-2 sm:bottom-0 sm:pb-[calc(0.5rem_+_env(safe-area-inset-bottom))]"
        >
          <div className="mx-auto max-w-app">
            {sendError && <p className="mb-1.5 px-1 text-[12.5px] text-brick">{sendError}</p>}
            {replyTo && (
              <div className="mb-1.5 flex items-center justify-between px-1 text-[12.5px] text-ink-soft">
                <span className="truncate">
                  <b className="font-semibold text-ink">{replyTo.author.nickname}</b>님에게 답글 쓰는 중
                </span>
                <button type="button" onClick={() => setReplyTo(null)} className="shrink-0 text-ink-faint underline underline-offset-4">
                  취소
                </button>
              </div>
            )}
            {/* 대화방 입력창과 같은 모양 (2026-11-22) */}
            <div className="flex items-end gap-1.5 rounded-[24px] border border-line bg-paper-card py-1 pl-4 pr-1 transition-colors focus-within:border-ink-soft">
              <textarea
                ref={inputRef}
                {...enterToSend}
                value={text}
                rows={1}
                maxLength={me?.config.comment_max ?? 500}
                placeholder={replyTo ? "답글 달기" : "댓글 달기"}
                aria-label="댓글"
                onChange={(e) => {
                  setText(e.target.value);
                  // 줄이 늘면 칸도 조금 늘어난다 (최대 약 4줄)
                  e.target.style.height = "auto";
                  e.target.style.height = `${Math.min(e.target.scrollHeight, 96)}px`;
                }}
                // 글자 16px: 아이폰은 이보다 작으면 누를 때 화면을 확대한다
                className="max-h-24 min-h-[40px] flex-1 resize-none bg-transparent py-2 text-[16px] leading-snug text-ink placeholder:text-ink-faint focus:outline-none sm:text-[15px]"
              />
              <button
                type="submit"
                aria-label="댓글 등록"
                disabled={sending || !text.trim()}
                onPointerDown={(e) => e.preventDefault()}
                className="mb-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-ink text-paper transition-opacity disabled:opacity-20"
              >
                <svg viewBox="0 0 16 16" className="h-4 w-4" aria-hidden>
                  <path d="M8 13V3M3.5 7.5L8 3l4.5 4.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
            </div>
          </div>
        </form>
      )}

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

/** 댓글을 "맨 위 댓글 + 그 밑 답글들"로 묶는다. 맨 위 댓글이 지워졌으면 root = null ("삭제된 댓글이에요") */
function threads(comments: BoardComment[]) {
  const roots = comments.filter((c) => !c.parent_id);
  const byRoot = new Map<string, BoardComment[]>();
  for (const c of comments) {
    if (!c.parent_id) continue;
    byRoot.set(c.parent_id, [...(byRoot.get(c.parent_id) ?? []), c]);
  }
  const out: { root: BoardComment | null; rootId: string; replies: BoardComment[] }[] = roots.map((r) => ({
    root: r,
    rootId: r.id,
    replies: byRoot.get(r.id) ?? [],
  }));
  // 맨 위 댓글이 지워진(또는 숨겨진) 답글 묶음
  for (const [rootId, replies] of byRoot) {
    if (!roots.some((r) => r.id === rootId)) out.push({ root: null, rootId, replies });
  }
  return out.sort((a, b) => Date.parse((a.root ?? a.replies[0]).created_at) - Date.parse((b.root ?? b.replies[0]).created_at));
}

function CommentItem({
  c,
  small,
  onAuthor,
  onReply,
  onDelete,
  onReport,
}: {
  c: BoardComment;
  small?: boolean;
  onAuthor: (profileId: string) => void;
  onReply?: (c: BoardComment) => void;
  onDelete: (id: string) => void;
  onReport: (id: string) => void;
}) {
  const pad = small ? "pl-[34px]" : "pl-[38px]";
  return (
    <div id={`c-${c.id}`} className="space-y-1.5">
      <AuthorLine
        author={c.author}
        size={small ? 24 : 28}
        onClick={!c.mine && c.author.id ? () => onAuthor(c.author.id!) : undefined}
        badge={c.by_post_author ? <span className="shrink-0 rounded bg-ink px-1.5 py-0.5 text-[10.5px] text-paper">글쓴이</span> : undefined}
        trailing={
          // 신고 버튼은 댓글 오른쪽 위 (2026-11-22)
          !c.mine ? (
            <button
              type="button"
              onClick={() => onReport(c.id)}
              className="shrink-0 pl-2 text-[12px] text-ink-faint underline underline-offset-4 hover:text-brick"
            >
              신고
            </button>
          ) : undefined
        }
      />
      <p className={`whitespace-pre-wrap break-words ${pad} text-[14.5px] leading-relaxed`}>
        {c.reply_to && <span className="mr-1 font-semibold text-ink-soft">@{c.reply_to}</span>}
        {c.body}
      </p>
      <div className={`flex items-center gap-3 ${pad} text-[12px] text-ink-faint`}>
        <span>{timeAgo(c.created_at)}</span>
        {onReply && (
          <button onClick={() => onReply(c)} className="underline underline-offset-4">
            답글
          </button>
        )}
        {c.mine && (
          <button onClick={() => onDelete(c.id)} className="underline underline-offset-4">
            삭제
          </button>
        )}
        {c.hidden && <span className="text-brick">신고로 숨겨짐</span>}
      </div>
    </div>
  );
}
