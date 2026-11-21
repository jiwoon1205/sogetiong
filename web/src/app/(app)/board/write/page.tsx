"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { Button, Field, Input, Notice, PageTitle, Spinner, Textarea } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { BOARD_NAMES, type BoardKey, type BoardMe, type BoardPost } from "@/lib/board";
import { cn } from "@/lib/format";

export default function WritePage() {
  return (
    <Suspense fallback={<Spinner />}>
      <Write />
    </Suspense>
  );
}

function Write() {
  const router = useRouter();
  const params = useSearchParams();
  const [me, setMe] = useState<BoardMe | null>(null);
  const [board, setBoard] = useState<BoardKey>((params.get("board") as BoardKey) || "FREE");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api<BoardMe>("/board/me")
      .then((m) => {
        if (!m.profile) router.replace("/board");
        setMe(m);
        if (!m.boards.find((b) => b.key === board)?.allowed) setBoard("FREE");
      })
      .catch((e) => setError(errorMessage(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function submit() {
    setSaving(true);
    setError("");
    try {
      const post = await api<BoardPost>("/board/posts", { method: "POST", body: { board, title, body } });
      router.replace(`/board/${post.id}`);
    } catch (e) {
      setError(errorMessage(e));
      setSaving(false);
    }
  }

  if (!me) return error ? <Notice tone="error">{error}</Notice> : <Spinner />;

  return (
    <div className="mx-auto max-w-app">
      <PageTitle eyebrow="게시판" title="글쓰기" />
      <div className="space-y-5">
        <div className="grid grid-cols-3 gap-2">
          {me.boards
            .filter((b) => b.allowed)
            .map((b) => (
              <button
                key={b.key}
                type="button"
                onClick={() => setBoard(b.key)}
                className={cn("h-10 rounded-md border text-[14px]", board === b.key ? "border-ink bg-ink text-paper" : "border-line bg-paper-card text-ink-soft")}
              >
                {BOARD_NAMES[b.key]}
              </button>
            ))}
        </div>
        <Field label="제목">
          <Input value={title} maxLength={me.config.title_max} onChange={(e) => setTitle(e.target.value)} />
        </Field>
        <Field label="내용" hint={`${body.length.toLocaleString()} / ${me.config.body_max.toLocaleString()}자 · 글만 쓸 수 있어요 · 하루 ${me.config.daily_posts}개까지`}>
          <Textarea value={body} rows={10} maxLength={me.config.body_max} onChange={(e) => setBody(e.target.value)} />
        </Field>
        <p className="text-[12.5px] leading-relaxed text-ink-faint">연락처·카톡 아이디·실명 같은 개인정보는 쓰지 마세요. 욕설·비하·개인정보 노출은 신고되면 지워지고 게시판 이용이 정지될 수 있어요.</p>
        {error && <Notice tone="error">{error}</Notice>}
        <div className="flex gap-2">
          <Button variant="secondary" className="flex-1" onClick={() => router.back()}>
            취소
          </Button>
          <Button className="flex-1" loading={saving} disabled={!title.trim() || !body.trim()} onClick={submit}>
            올리기
          </Button>
        </div>
      </div>
    </div>
  );
}
