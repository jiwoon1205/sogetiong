"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { AuthFrame } from "@/components/AuthFrame";
import { Button, Notice, PageTitle, Textarea } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";

/**
 * 개선점·바라는 기능 설문 (2026-11-14, 옛 "정식 오픈 전 설문"을 바꿈)
 * - 관리자가 설문을 켜면, 아직 답하지 않은 사람은 로그인·가입 직후 이 화면을 먼저 본다 (SessionGate에서 띄움)
 * - 질문 2개, 둘 다 글로 답한다. 하나 이상 적어야 제출된다
 * - 쓸 말이 없으면 "건너뛰기" → 다시 안 뜬다. 계정당 한 번만
 * - 규칙은 백엔드 app/services/survey_service.py 맨 위 설명
 */
export function SurveyScreen({ onDone }: { onDone: () => Promise<void> }) {
  const router = useRouter();
  const [improvement, setImprovement] = useState("");
  const [featureRequest, setFeatureRequest] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState<"submit" | "skip" | null>(null);

  const ready = improvement.trim() !== "" || featureRequest.trim() !== "";

  async function send(skip: boolean) {
    if (!skip && !ready) {
      setError("둘 중 하나는 적어주세요. 쓸 말이 없으면 '건너뛰기'를 눌러주세요.");
      return;
    }
    setError("");
    setLoading(skip ? "skip" : "submit");
    try {
      await api("/me/survey", {
        method: "POST",
        body: skip ? { skip: true } : { improvement, feature_request: featureRequest },
      });
      await onDone(); // /me 를 다시 읽으면 설문이 사라지고 원래 화면이 나온다
    } catch (err) {
      setError(errorMessage(err));
      setLoading(null);
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
        eyebrow="훕팅 의견 설문"
        title="훕팅을 같이 만들어 주세요"
        desc="1분이면 끝나요. 적어 주신 의견은 운영자만 보고, 서비스를 고치는 데만 써요. 다른 학생에게는 보이지 않아요."
      />

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void send(false);
        }}
        className="space-y-8"
      >
        <section className="space-y-3">
          <Question no={1} title="훕팅에서 불편했거나 개선했으면 하는 점이 있나요?" />
          <Textarea
            value={improvement}
            onChange={(e) => setImprovement(e.target.value)}
            maxLength={1000}
            placeholder="예) 추천이 너무 빨리 끝나요, 채팅 화면이 불편해요"
            aria-label="개선했으면 하는 점"
          />
        </section>

        <section className="space-y-3">
          <Question no={2} title="새로 생겼으면 하는 기능이 있나요?" />
          <Textarea
            value={featureRequest}
            onChange={(e) => setFeatureRequest(e.target.value)}
            maxLength={1000}
            placeholder="예) 관심사로 추천받기, 채팅에서 사진 보내기"
            aria-label="새로 생겼으면 하는 기능"
          />
        </section>

        <p className="text-[13px] text-ink-faint">둘 중 하나만 적어도 괜찮아요.</p>

        {error && <Notice tone="error">{error}</Notice>}
        <div className="space-y-2">
          <Button type="submit" size="lg" className="w-full" loading={loading === "submit"} disabled={loading !== null}>
            제출하기
          </Button>
          <Button
            type="button"
            variant="ghost"
            className="w-full"
            loading={loading === "skip"}
            disabled={loading !== null}
            onClick={() => void send(true)}
          >
            건너뛰기
          </Button>
        </div>
      </form>
    </AuthFrame>
  );
}

function Question({ no, title }: { no: number; title: string }) {
  return (
    <h2 className="flex gap-2 text-[15.5px] font-semibold leading-snug text-ink">
      <span className="num text-ink-faint">{no}.</span>
      <span>{title}</span>
    </h2>
  );
}
