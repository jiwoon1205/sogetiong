"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ProfileCard } from "@/components/ProfileCard";
import { Button, ButtonLink, Notice, Spinner } from "@/components/ui";
import { ApiError, api, errorMessage } from "@/lib/api";
import type { Card } from "@/lib/types";

type State =
  | { kind: "loading" }
  | { kind: "cards"; cards: Card[] }
  | { kind: "blocked"; code: string }
  | { kind: "error"; message: string };

const BLOCKED_COPY: Record<string, { title: string; body: string; href: string; cta: string }> = {
  PROFILE_REQUIRED: { title: "프로필을 먼저 작성해주세요", body: "추천을 받으려면 공개 프로필이 필요해요.", href: "/onboarding", cta: "프로필 작성" },
  PREFERENCES_REQUIRED: { title: "매칭 조건을 정해주세요", body: "어떤 사람을 만나고 싶은지 알려주면 추천을 시작할게요.", href: "/settings", cta: "매칭 조건 설정" },
  PHOTO_APPROVAL_REQUIRED: {
    title: "사진 검수를 기다리고 있어요",
    body: "운영진이 사진을 확인하고 평가를 마치면 추천이 열려요. 보통 하루 안에 끝나요.",
    href: "/profile",
    cta: "검수 상태 보기",
  },
};

export default function DiscoverPage() {
  const [state, setState] = useState<State>({ kind: "loading" });
  const [busy, setBusy] = useState(false);
  const [matched, setMatched] = useState<{ card: Card; matchId: string } | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const res = await api<{ profiles: Card[] }>("/discover");
      setState({ kind: "cards", cards: res.profiles });
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) setState({ kind: "blocked", code: err.code });
      else setState({ kind: "error", message: errorMessage(err) });
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const act = useCallback(
    async (action: "like" | "pass") => {
      if (state.kind !== "cards" || !state.cards[0] || busy) return;
      const card = state.cards[0];
      setBusy(true);
      setError("");
      try {
        if (action === "like") {
          const res = await api<{ matched: boolean; match_id: string | null }>("/likes", { method: "POST", body: { profile_id: card.profile_id } });
          if (res.matched && res.match_id) setMatched({ card, matchId: res.match_id });
        } else {
          await api("/passes", { method: "POST", body: { profile_id: card.profile_id } });
        }
        const rest = state.cards.slice(1);
        if (rest.length === 0) await load();
        else setState({ kind: "cards", cards: rest });
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setBusy(false);
      }
    },
    [state, busy, load],
  );

  // 키보드: ← 넘기기, → 좋아요
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (matched || (e.target as HTMLElement)?.tagName === "INPUT") return;
      if (e.key === "ArrowLeft") act("pass");
      if (e.key === "ArrowRight") act("like");
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [act, matched]);

  if (state.kind === "loading") return <Spinner label="오늘의 추천을 고르는 중" />;
  if (state.kind === "error") return <Notice tone="error">{state.message}</Notice>;
  if (state.kind === "blocked") {
    const copy = BLOCKED_COPY[state.code] ?? BLOCKED_COPY.PROFILE_REQUIRED;
    return (
      <EmptyState title={copy.title} body={copy.body}>
        <ButtonLink href={copy.href}>{copy.cta}</ButtonLink>
      </EmptyState>
    );
  }
  if (state.cards.length === 0) {
    return (
      <EmptyState title="지금은 조건에 맞는 사람이 없어요" body="매칭 범위를 넓히면 더 많은 프로필을 볼 수 있어요. 조건은 자동으로 바뀌지 않아요.">
        <ButtonLink href="/settings" variant="secondary">
          매칭 조건 바꾸기
        </ButtonLink>
        <Button variant="ghost" onClick={load}>
          다시 불러오기
        </Button>
      </EmptyState>
    );
  }

  const [current, next] = state.cards;
  return (
    <div className="mx-auto max-w-app">
      <div className="mb-5 flex items-baseline justify-between">
        <p className="eyebrow">오늘의 추천</p>
        <p className="num text-[12.5px] text-ink-faint">{state.cards.length}명 남음</p>
      </div>

      <SwipeCard key={current.profile_id} onSwipe={act} disabled={busy}>
        <ProfileCard card={current} />
      </SwipeCard>
      {next && <div aria-hidden className="mx-4 -mt-2 h-3 rounded-b-card border border-t-0 border-line bg-paper-deep" />}

      {error && <div className="mt-4"><Notice tone="error">{error}</Notice></div>}

      <div className="mt-6 grid grid-cols-2 gap-3">
        <Button variant="secondary" size="lg" onClick={() => act("pass")} disabled={busy}>
          넘기기
        </Button>
        <Button size="lg" onClick={() => act("like")} disabled={busy}>
          좋아요
        </Button>
      </div>
      <p className="mt-4 hidden text-center text-[12px] text-ink-faint sm:block">키보드 ← 넘기기 · → 좋아요</p>
      <p className="mt-4 text-center text-[12px] text-ink-faint sm:hidden">카드를 옆으로 밀어도 돼요</p>

      {matched && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-paper/95 px-6">
          <div className="w-full max-w-sm text-center">
            <p className="eyebrow mb-4 text-brick">서로 좋아요</p>
            <h2 className="font-serif text-[30px] font-semibold leading-snug">
              {matched.card.nickname}님과
              <br />
              마음이 맞았어요
            </h2>
            <p className="mt-4 text-[14.5px] leading-relaxed text-ink-soft">이름도 얼굴도 모르는 채로, 대화부터 시작해보세요.</p>
            <div className="mt-8 space-y-3">
              <ButtonLink href={`/chat/${matched.matchId}`} size="lg" className="w-full">
                대화 시작하기
              </ButtonLink>
              <Button variant="ghost" className="w-full" onClick={() => setMatched(null)}>
                계속 둘러보기
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function EmptyState({ title, body, children }: { title: string; body: string; children?: React.ReactNode }) {
  return (
    <div className="mx-auto max-w-app py-16 text-center">
      <div className="mx-auto mb-8 h-px w-12 bg-ink" />
      <h1 className="font-serif text-[23px] font-semibold">{title}</h1>
      <p className="mx-auto mt-3 max-w-xs text-[14.5px] leading-relaxed text-ink-soft">{body}</p>
      <div className="mt-8 flex flex-wrap justify-center gap-3">{children}</div>
    </div>
  );
}

/** 모바일에서 카드를 좌우로 밀어서 넘기기/좋아요 */
function SwipeCard({ children, onSwipe, disabled }: { children: React.ReactNode; onSwipe: (a: "like" | "pass") => void; disabled?: boolean }) {
  const start = useRef<number | null>(null);
  const [dx, setDx] = useState(0);
  const THRESHOLD = 110;

  return (
    <div
      className="relative touch-pan-y select-none"
      style={{ transform: `translateX(${dx}px) rotate(${dx / 40}deg)`, transition: start.current === null ? "transform 200ms ease" : "none" }}
      onPointerDown={(e) => {
        if (disabled || e.pointerType === "mouse") return;
        start.current = e.clientX;
      }}
      onPointerMove={(e) => start.current !== null && setDx(e.clientX - start.current)}
      onPointerUp={() => {
        if (start.current === null) return;
        start.current = null;
        if (dx > THRESHOLD) onSwipe("like");
        else if (dx < -THRESHOLD) onSwipe("pass");
        setDx(0);
      }}
      onPointerCancel={() => {
        start.current = null;
        setDx(0);
      }}
    >
      {Math.abs(dx) > 30 && (
        <span
          className="absolute left-1/2 top-6 z-10 -translate-x-1/2 rounded-sm border px-3 py-1 text-[13px] font-semibold"
          style={{ opacity: Math.min(1, Math.abs(dx) / THRESHOLD) }}
        >
          <span className={dx > 0 ? "text-brick" : "text-ink-soft"}>{dx > 0 ? "좋아요" : "넘기기"}</span>
        </span>
      )}
      {children}
    </div>
  );
}
