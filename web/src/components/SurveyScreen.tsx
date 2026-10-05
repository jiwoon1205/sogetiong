"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { AuthFrame } from "@/components/AuthFrame";
import { Button, Notice, PageTitle, Textarea } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { cn } from "@/lib/format";

/**
 * 정식 오픈 전 설문 (2026-10-05)
 * - 관리자가 설문을 켜면, 아직 답하지 않은 사람은 로그인·가입 직후 이 화면만 본다 (SessionGate에서 띄움)
 * - 꼭 답해야 넘어간다. 계정당 한 번만. 답하면 다시 안 뜬다
 * - 보기 이름(key)은 백엔드 app/services/survey_service.py 와 같아야 한다
 */

type AppearanceKey = "AI_ONLY" | "AI_NEW_CRITERIA" | "AI_PLUS_ADMIN" | "ADMIN_ONLY" | "OTHER";

const APPEARANCE_OPTIONS: { value: AppearanceKey; label: string; desc?: string }[] = [
  { value: "AI_ONLY", label: "지금처럼 AI가 평가", desc: "전체적인 인상 · 스타일 · 자기관리 · 사진 분위기 4가지 기준 그대로" },
  { value: "AI_NEW_CRITERIA", label: "AI가 평가하되, 기준을 바꾸기", desc: "평가 항목을 다른 것으로 바꿔요" },
  { value: "AI_PLUS_ADMIN", label: "AI 점수 + 운영자 조정", desc: "AI가 매긴 점수를 운영자가 한 번 더 보고 ±2점까지 고쳐서 최종 점수를 정해요" },
  { value: "ADMIN_ONLY", label: "운영자가 직접 평가", desc: "AI 없이 운영자 혼자 평가해요" },
  { value: "OTHER", label: "기타", desc: "원하는 방식을 직접 적어주세요" },
];

const RATING_OPTIONS: { value: number; label: string }[] = [
  { value: 5, label: "매우 만족" },
  { value: 4, label: "만족" },
  { value: 3, label: "보통" },
  { value: 2, label: "불만족" },
  { value: 1, label: "매우 불만족" },
];

export function SurveyScreen({ onDone }: { onDone: () => Promise<void> }) {
  const router = useRouter();
  const [appearance, setAppearance] = useState<AppearanceKey | null>(null);
  const [appearanceComment, setAppearanceComment] = useState("");
  const [rating, setRating] = useState<number | null>(null);
  const [paymentComment, setPaymentComment] = useState("");
  const [suggestion, setSuggestion] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const needsComment = appearance === "OTHER";
  const showComment = appearance === "AI_NEW_CRITERIA" || appearance === "OTHER";
  const ready = appearance !== null && rating !== null && (!needsComment || appearanceComment.trim() !== "");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!ready) {
      setError(needsComment && appearance ? "'기타'를 골랐다면 원하는 방식을 적어주세요." : "1번과 2번 질문에 답해주세요.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      await api("/me/survey", {
        method: "POST",
        body: {
          appearance_choice: appearance,
          appearance_comment: showComment ? appearanceComment : null,
          payment_rating: rating,
          payment_comment: paymentComment,
          suggestion,
        },
      });
      await onDone(); // /me 를 다시 읽으면 설문이 사라지고 원래 화면이 나온다
    } catch (err) {
      setError(errorMessage(err));
      setLoading(false);
      // 이미 답했거나 설문이 끝난 경우에도 원래 화면으로 보내준다
      await onDone().catch(() => {});
    }
  }

  async function logout() {
    await api("/auth/logout", { method: "POST" }).catch(() => {});
    router.replace("/login");
  }

  return (
    <AuthFrame
      footer={
        <button type="button" onClick={logout} className="underline underline-offset-4 hover:text-ink">
          로그아웃
        </button>
      }
    >
      <PageTitle
        eyebrow="정식 오픈 전 설문"
        title="훕팅을 같이 만들어 주세요"
        desc="1분이면 끝나요. 답해 주셔야 서비스를 이용할 수 있고, 계정당 한 번만 참여해요. 답한 내용은 서비스를 고치는 데만 쓰고 다른 학생에게는 보이지 않아요."
      />

      <form onSubmit={submit} className="space-y-10">
        {/* 1. 외모 평가 방식 */}
        <section className="space-y-3">
          <Question no={1} title="정식 오픈 후 외모 평가는 어떻게 하면 좋을까요?" />
          <div className="space-y-2" role="radiogroup" aria-label="외모 평가 방식">
            {APPEARANCE_OPTIONS.map((o) => (
              <Choice key={o.value} selected={appearance === o.value} onClick={() => setAppearance(o.value)} label={o.label} desc={o.desc} />
            ))}
          </div>
          {showComment && (
            <Textarea
              value={appearanceComment}
              onChange={(e) => setAppearanceComment(e.target.value)}
              maxLength={500}
              placeholder={needsComment ? "원하는 평가 방식을 적어주세요 (필수)" : "어떤 기준이면 좋을지 적어주세요 (선택)"}
              aria-label="외모 평가 의견"
            />
          )}
        </section>

        {/* 2. 유료 시스템 만족도 */}
        <section className="space-y-3">
          <Question no={2} title="정식 오픈 후 유료 방식, 마음에 드시나요?" />
          <div className="rounded-md border border-line bg-paper-deep px-4 py-3 text-[13.5px] leading-relaxed text-ink-soft">
            <ul className="list-disc space-y-1 pl-4">
              <li>
                기본 이용권 <b className="text-ink">4주 3,000원</b>
              </li>
              <li>
                VIP <b className="text-ink">4주 6,000원</b> (기본 포함) — 하루 LIKE 5+5개, 받은 LIKE 목록, PASS한 사람 24시간 뒤 다시 추천, 사진 재검토 3일
              </li>
              <li>자동 결제 없이 통장 입금 (입금자명 = 결제 코드)</li>
              <li>이용권이 끝나도 대화는 계속할 수 있어요</li>
            </ul>
          </div>
          <div className="space-y-2" role="radiogroup" aria-label="유료 방식 만족도">
            {RATING_OPTIONS.map((o) => (
              <Choice key={o.value} selected={rating === o.value} onClick={() => setRating(o.value)} label={o.label} compact />
            ))}
          </div>
          <Textarea
            value={paymentComment}
            onChange={(e) => setPaymentComment(e.target.value)}
            maxLength={500}
            placeholder="그렇게 생각한 이유가 있다면 적어주세요 (선택)"
            aria-label="유료 방식 의견"
          />
        </section>

        {/* 3. 기타 개선점 */}
        <section className="space-y-3">
          <Question no={3} title="그 밖에 고쳤으면 하는 점이나 바라는 기능이 있나요?" optional />
          <Textarea
            value={suggestion}
            onChange={(e) => setSuggestion(e.target.value)}
            maxLength={1000}
            placeholder="없으면 비워두셔도 돼요"
            aria-label="기타 개선점"
          />
        </section>

        {error && <Notice tone="error">{error}</Notice>}
        <Button type="submit" size="lg" className="w-full" loading={loading}>
          제출하고 시작하기
        </Button>
      </form>
    </AuthFrame>
  );
}

function Question({ no, title, optional }: { no: number; title: string; optional?: boolean }) {
  return (
    <h2 className="flex gap-2 text-[15.5px] font-semibold leading-snug text-ink">
      <span className="num text-ink-faint">{no}.</span>
      <span>
        {title}
        {optional && <span className="ml-1.5 text-[13px] font-normal text-ink-faint">(선택)</span>}
      </span>
    </h2>
  );
}

function Choice({
  selected,
  onClick,
  label,
  desc,
  compact,
}: {
  selected: boolean;
  onClick: () => void;
  label: string;
  desc?: string;
  compact?: boolean;
}) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      onClick={onClick}
      className={cn(
        "flex w-full items-start gap-3 rounded-md border px-4 text-left transition-colors",
        compact ? "py-2.5" : "py-3",
        selected ? "border-ink bg-paper-card" : "border-line bg-paper-card/60 hover:border-line-strong",
      )}
    >
      <span
        aria-hidden
        className={cn(
          "mt-[3px] flex h-[16px] w-[16px] shrink-0 items-center justify-center rounded-full border",
          selected ? "border-ink" : "border-line-strong",
        )}
      >
        {selected && <span className="h-2 w-2 rounded-full bg-ink" />}
      </span>
      <span>
        <span className={cn("block text-[14.5px]", selected ? "font-semibold text-ink" : "text-ink")}>{label}</span>
        {desc && <span className="mt-0.5 block text-[12.5px] leading-relaxed text-ink-faint">{desc}</span>}
      </span>
    </button>
  );
}
