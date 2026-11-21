"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AuthorLine } from "@/components/board/AuthorLine";
import { ProfileEditor } from "@/components/board/ProfileEditor";
import { Button, Modal, Notice, PageTitle, Spinner } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { BOARD_NAMES, banText, type BoardKey, type BoardMe, type BoardPost } from "@/lib/board";
import { cn, timeAgo } from "@/lib/format";

const BOARD_KEY = "board:last";

/**
 * 게시판 탭 (2026-11-22).
 * 처음엔 게시판 프로필이 없다 → "게시판을 이용할래요?" + 프로필 만들기.
 * 게시판 3개: 자유(모두) · 연애(진지한 연애) · 캐주얼(캐주얼한 만남). 들어갈 수 없는 게시판은 잠금 표시.
 */
export default function BoardPage() {
  const [me, setMe] = useState<BoardMe | null>(null);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState(false);

  const loadMe = useCallback(
    () =>
      api<BoardMe>("/board/me")
        .then(setMe)
        .catch((e) => setError(errorMessage(e))),
    [],
  );
  useEffect(() => {
    void loadMe();
  }, [loadMe]);

  if (error) return <Notice tone="error">{error}</Notice>;
  if (!me) return <Spinner />;

  if (!me.profile) {
    return (
      <div className="mx-auto max-w-app">
        <PageTitle eyebrow="게시판" title={creating ? "게시판 프로필 만들기" : "게시판을 이용해 볼까요?"} />
        {creating ? (
          <ProfileEditor me={me} onSaved={() => void loadMe()} onCancel={() => setCreating(false)} />
        ) : (
          <div className="space-y-5">
            <div className="rounded-card border border-line bg-paper-card px-5 py-6 text-[14.5px] leading-relaxed text-ink-soft">
              <p className="font-semibold text-ink">같은 학교 사람들과 자유롭게 이야기하는 곳이에요.</p>
              <ul className="mt-3 list-disc space-y-1.5 pl-5">
                <li>게시판 전용 프로필(새 닉네임)을 따로 만들어요. 소개팅 프로필은 게시판에서 절대 보이지 않아요.</li>
                <li>다른 사람에게는 프사 · 닉네임 · 성별 · 학교만 보여요. 원하면 내 점수 하나를 공개할 수 있어요.</li>
                <li>
                  게시판은 3개예요: <b>자유</b>(모두) · <b>연애</b>(진지한 연애를 고른 사람) · <b>캐주얼</b>(캐주얼한 만남을 고른 사람)
                </li>
                <li>마음에 드는 사람에게 쪽지를 보낼 수 있어요 (슈퍼 라이크 1개, 여성은 하루 3개 무료).</li>
              </ul>
            </div>
            {me.can_create ? (
              <Button className="w-full" size="lg" onClick={() => setCreating(true)}>
                게시판 프로필 만들기
              </Button>
            ) : (
              <Notice>사진 검수가 끝나면 게시판을 이용할 수 있어요.</Notice>
            )}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-app">
      <div className="mb-6 flex items-center justify-between gap-3">
        <div className="min-w-0 flex-1">
          <AuthorLine author={me.profile} size={40} onClick={() => setEditing(true)} trailing={
              <button type="button" onClick={() => setEditing(true)} className="shrink-0 text-[12.5px] text-ink-faint underline underline-offset-4">
                프로필 수정
              </button>
            } />
        </div>
      </div>

      {me.profile.banned_until && (
        <div className="mb-5">
          <Notice tone="error">
            <b>게시판 이용 정지 중 ({banText(me.profile)})</b>
            <br />
            사유: {me.profile.ban_reason}
            <br />
            글·댓글·쪽지 보내기를 할 수 없어요. 읽기와 소개팅은 그대로 쓸 수 있어요.
          </Notice>
        </div>
      )}

      <PostList me={me} />

      <Modal open={editing} onClose={() => setEditing(false)} title="게시판 프로필 수정">
        <ProfileEditor
          me={me}
          onSaved={() => {
            setEditing(false);
            void loadMe();
          }}
          onCancel={() => setEditing(false)}
        />
      </Modal>
    </div>
  );
}

function PostList({ me }: { me: BoardMe }) {
  const [board, setBoard] = useState<BoardKey>(() => {
    if (typeof window === "undefined") return "FREE";
    try {
      const saved = sessionStorage.getItem(BOARD_KEY) as BoardKey | null;
      return saved && me.boards.find((b) => b.key === saved)?.allowed ? saved : "FREE";
    } catch {
      return "FREE";
    }
  });
  const [posts, setPosts] = useState<BoardPost[] | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [locked, setLocked] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setPosts(null);
    setError("");
    try {
      sessionStorage.setItem(BOARD_KEY, board);
    } catch {}
    api<{ posts: BoardPost[]; has_more: boolean }>(`/board/posts?board=${board}`)
      .then((r) => {
        setPosts(r.posts);
        setHasMore(r.has_more);
      })
      .catch((e) => setError(errorMessage(e)));
  }, [board]);

  async function more() {
    if (!posts?.length) return;
    setLoadingMore(true);
    try {
      const last = posts[posts.length - 1].created_at;
      const r = await api<{ posts: BoardPost[]; has_more: boolean }>(`/board/posts?board=${board}&before=${encodeURIComponent(last)}`);
      setPosts([...posts, ...r.posts]);
      setHasMore(r.has_more);
    } finally {
      setLoadingMore(false);
    }
  }

  const info = me.boards.find((b) => b.key === board)!;

  return (
    <>
      <div className="mb-3 grid grid-cols-3 rounded-md border border-line bg-paper-card p-1" role="tablist">
        {me.boards.map((b) => (
          <button
            key={b.key}
            role="tab"
            aria-selected={board === b.key}
            onClick={() => (b.allowed ? setBoard(b.key) : setLocked(b.key === "LOVE" ? "연애 게시판은 찾는 관계가 '진지한 연애'인 사람만 들어갈 수 있어요." : "캐주얼 게시판은 찾는 관계가 '캐주얼한 만남'인 사람만 들어갈 수 있어요."))}
            className={cn(
              "h-9 rounded-[5px] text-[14px] transition-colors",
              board === b.key ? "bg-ink text-paper" : b.allowed ? "text-ink-soft hover:text-ink" : "text-ink-faint",
            )}
          >
            {!b.allowed && "🔒 "}
            {BOARD_NAMES[b.key]}
          </button>
        ))}
      </div>
      {locked && (
        <div className="mb-3">
          <Notice>
            {locked}{" "}
            <Link href="/profile" className="underline underline-offset-4">
              찾는 관계 바꾸기
            </Link>
          </Notice>
        </div>
      )}
      <p className="eyebrow mb-4">{info.name}</p>

      {/* 글쓰기 버튼 (2026-11-22): 화면 아래 가운데에 떠 있다. 휴대폰은 아래 탭 바로 위 */}
      {!me.profile?.banned_until && (
        <Link
          href={`/board/write?board=${board}`}
          className="fixed bottom-[calc(5.75rem_+_env(safe-area-inset-bottom))] left-1/2 z-20 flex h-12 -translate-x-1/2 items-center gap-2 rounded-full bg-ink px-6 text-[15px] font-medium text-paper shadow-lg sm:bottom-8"
        >
          <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
            <path d="M13.5 3.5l3 3L7 16H4v-3l9.5-9.5z" strokeLinejoin="round" />
          </svg>
          글쓰기
        </Link>
      )}

      {error ? (
        <Notice tone="error">{error}</Notice>
      ) : !posts ? (
        <Spinner />
      ) : posts.length === 0 ? (
        <p className="rounded-card border border-line bg-paper-card px-6 py-12 text-center text-[14px] text-ink-soft">아직 글이 없어요. 첫 글을 써 보세요!</p>
      ) : (
        <ul className="divide-y divide-line border-y border-line">
          {posts.map((p) => (
            <li key={p.id}>
              <Link href={`/board/${p.id}`} className="block py-4 transition-colors hover:bg-paper-deep/60">
                <p className="truncate text-[15.5px] font-semibold text-ink">{p.title}</p>
                <p className="mt-1 line-clamp-2 text-[13.5px] leading-relaxed text-ink-soft">{p.body}</p>
                <div className="mt-2 flex items-center gap-2 text-[12px] text-ink-faint">
                  <span className="truncate">{p.author.nickname}</span>
                  <span>·</span>
                  <span className="shrink-0">{timeAgo(p.created_at)}</span>
                  {p.comment_count > 0 && <span className="shrink-0 text-brick">💬 {p.comment_count}</span>}
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
      {hasMore && (
        <Button variant="secondary" className="mt-4 w-full" loading={loadingMore} onClick={more}>
          더 보기
        </Button>
      )}
      {/* 떠 있는 글쓰기 버튼에 마지막 글이 가리지 않게 */}
      <div className="h-20" aria-hidden />
    </>
  );
}
