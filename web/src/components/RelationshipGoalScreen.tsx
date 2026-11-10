"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { AuthFrame } from "@/components/AuthFrame";
import { Button, Notice, PageTitle, Tag } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { RELATIONSHIP_GOALS, type RelationshipGoal } from "@/lib/types";

/**
 * 프로필 업데이트: 내가 찾는 관계 (2026-11-11)
 * - '내가 찾는 관계'(2026-10-24)가 생기기 전에 프로필을 다 쓴 회원은 이 화면만 본다 (SessionGate에서 띄움)
 * - 꼭 골라야 넘어간다. 고르면 /me를 다시 읽어 원래 화면으로 돌아간다
 * - 고른 값은 나중에 내 프로필 → 프로필 수정에서 바꿀 수 있다
 */
export function RelationshipGoalScreen({ onDone }: { onDone: () => Promise<void> }) {
  const router = useRouter();
  const [goal, setGoal] = useState<RelationshipGoal | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!goal) return setError("내가 찾는 관계를 골라주세요.");
    setError("");
    setLoading(true);
    try {
      await api("/me/profile", { method: "PATCH", body: { relationship_goal: goal } });
      await onDone();
    } catch (err) {
      setError(errorMessage(err));
      setLoading(false);
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
        eyebrow="프로필 업데이트"
        title="어떤 관계를 찾고 있나요?"
        desc="프로필에 '내가 찾는 관계'가 새로 생겼어요. 골라 주셔야 서비스를 계속 이용할 수 있어요. 고른 뒤 3일이 지나면 내 프로필에서 바꿀 수 있어요."
      />

      <form onSubmit={submit} className="space-y-6">
        <div className="space-y-2">
          <p className="text-[13px] font-medium text-ink-soft">
            내가 찾는 관계 <span className="text-ink-faint">· 필수, 1개</span>
          </p>
          <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="내가 찾는 관계">
            {RELATIONSHIP_GOALS.map((g) => (
              <Tag key={g.value} active={goal === g.value} onClick={() => setGoal(g.value)}>
                {g.label}
              </Tag>
            ))}
          </div>
          <p className="text-[12.5px] leading-relaxed text-ink-faint">다른 학생 카드에 보여요. 추천에는 영향이 없어요.</p>
        </div>

        {/* ProfileForm과 같은 안내 (2026-10-24 사용자 결정) */}
        <div className="rounded-card border border-brick/30 bg-brick-wash px-4 py-3 text-[12.5px] leading-relaxed text-ink-soft">
          <b className="font-semibold text-brick-deep">⚠️ 꼭 읽어주세요</b>
          <br />
          &lsquo;캐주얼한 만남&rsquo;을 고르지 않고 <b className="font-semibold text-ink">파트너·FWB·원나잇</b> 같은 불건전한 만남을 요구하다 신고로
          확인되면 <b className="font-semibold text-ink">영구 정지</b>돼요.
        </div>

        {error && <Notice tone="error">{error}</Notice>}
        <Button type="submit" loading={loading} disabled={!goal} className="w-full">
          저장하고 계속하기
        </Button>
      </form>
    </AuthFrame>
  );
}
