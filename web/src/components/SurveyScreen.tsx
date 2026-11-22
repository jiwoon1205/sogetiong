"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { AuthFrame } from "@/components/AuthFrame";
import { Button, Notice, PageTitle, Textarea } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { cn } from "@/lib/format";

/**
 * 개선사항 찬반 투표 (2026-11-22): 찾는 관계 '대학교 친구'를 없앨까요?
 * - 모든 사용자에게, 아직 답하지 않았으면 로그인·가입 직후 이 화면이 먼저 뜬다 (SessionGate에서 띄움)
 * - 찬성/반대를 꼭 골라야 제출된다. 하고 싶은 말은 선택. 계정당 한 번만
 * - 규칙은 백엔드 app/services/survey_service.py 맨 위 설명
 */
type Vote = "AGREE" | "DISAGREE";

const CHOICES: { value: Vote; title: string; desc: string }[] = [
  { value: "AGREE", title: "찬성", desc: "'대학교 친구'를 없애 주세요" },
  { value: "DISAGREE", title: "반대", desc: "'대학교 친구'를 남겨 주세요" },
];

export function SurveyScreen({ onDone }: { onDone: () => Promise<void> }) {
  const router = useRouter();
  const [vote, setVote] = useState<Vote | null>(null);
  const [comment, setComment] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function send() {
    if (!vote) {
      setError("찬성 또는 반대를 골라 주세요.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      await api("/me/survey", { method: "POST", body: { vote, comment } });
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
      <PageTitle eyebrow="훕팅 개선사항 투표" title="찾는 관계에서 '대학교 친구'를 없앨까요?" />

      <p className="mb-8 rounded-md border border-line bg-paper-deep px-4 py-3 text-[13.5px] leading-relaxed text-ink-soft">
        많은 분들이 훕팅 설문에서 찾는 관계의 <b className="font-semibold text-ink">&apos;대학교 친구&apos;를 없애 달라고</b> 요청해 주셨어요. 바꾸기 전에 여러분의 생각을 듣고
        싶어요. 투표 결과는 운영자만 보고, 다른 학생에게는 보이지 않아요.
      </p>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void send();
        }}
        className="space-y-7"
      >
        <div className="grid grid-cols-2 gap-3" role="radiogroup" aria-label="찬반">
          {CHOICES.map((c) => (
            <button
              key={c.value}
              type="button"
              role="radio"
              aria-checked={vote === c.value}
              onClick={() => {
                setVote(c.value);
                setError("");
              }}
              className={cn(
                "rounded-card border px-4 py-5 text-center transition-colors",
                vote === c.value ? "border-ink bg-ink text-paper" : "border-line bg-paper-card text-ink hover:border-line-strong",
              )}
            >
              <span className="block text-[18px] font-semibold">{c.title}</span>
              <span className={cn("mt-1 block text-[13px]", vote === c.value ? "text-paper/80" : "text-ink-soft")}>{c.desc}</span>
            </button>
          ))}
        </div>

        <section className="space-y-2">
          <p className="text-[14px] font-medium text-ink">하고 싶은 말 (선택)</p>
          <Textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            maxLength={1000}
            placeholder="예) 친구 찾는 사람이 섞여 있어서 헷갈려요"
            aria-label="하고 싶은 말"
          />
        </section>

        {error && <Notice tone="error">{error}</Notice>}
        <Button type="submit" size="lg" className="w-full" loading={loading}>
          투표하기
        </Button>
      </form>
    </AuthFrame>
  );
}
