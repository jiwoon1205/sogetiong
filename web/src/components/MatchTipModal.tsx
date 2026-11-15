"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, Modal } from "@/components/ui";
import { api } from "@/lib/api";
import type { MatchTip } from "@/lib/types";

/** 매칭 확률 높이기 안내 팝업 (2026-11-16, 이탈 막기).
 *  남성 · 접속한 날 3일 이상 · 매칭 0회일 때 한 번만. 닫으면 서버에 기록 → 알림 목록에 같은 내용이 남는다.
 *  공지 팝업이 떠 있을 때는 겹치지 않게 띄우지 않는다 (layout에서). */
export function MatchTipModal({ tip }: { tip?: MatchTip | null }) {
  const router = useRouter();
  const [closed, setClosed] = useState(false);
  if (!tip || closed) return null;

  function close() {
    setClosed(true);
    void api("/me/match-tip/seen", { method: "POST" }).catch(() => {});
  }

  const checks: { ok: boolean; text: string }[] = [
    {
      ok: tip.bio_good,
      text: tip.bio_good
        ? `자기소개 ${tip.bio_chars}자 · 충분해요`
        : `자기소개 ${tip.bio_chars}자 → ${tip.good_bio_chars}자 넘게 써 보세요`,
    },
    {
      ok: tip.interests_good,
      text: tip.interests_good ? `관심사 ${tip.interests}개 · 좋아요` : `관심사 ${tip.interests}개 → ${tip.good_interests}개 이상 골라 보세요`,
    },
    { ok: tip.mbti_set, text: tip.mbti_set ? "MBTI 적음" : "MBTI를 적어 보세요" },
  ];

  return (
    <Modal open onClose={close} title="매칭 확률을 높이는 방법">
      <p className="text-[14px] leading-relaxed text-ink-soft">
        아직 매칭이 없어서 도움이 될 만한 것을 모았어요. 훕팅 데이터를 보면 프로필을 꼼꼼히 채운 사람이 매칭이 훨씬 많았어요.
      </p>

      <div className="mt-4 rounded-card border border-line bg-paper-card px-4 py-3">
        <p className="text-[13px] font-semibold text-ink">내 프로필 점검</p>
        <ul className="mt-2 space-y-1.5 text-[14px]">
          {checks.map((c) => (
            <li key={c.text} className="flex items-start gap-2">
              <span className={c.ok ? "text-ink-faint" : "text-brick"} aria-hidden>
                {c.ok ? "✓" : "●"}
              </span>
              <span className={c.ok ? "text-ink-soft" : "text-ink"}>{c.text}</span>
            </li>
          ))}
        </ul>
      </div>

      <ul className="mt-4 space-y-2.5 text-[14px] leading-relaxed text-ink-soft">
        <li>
          ✍️ <b className="font-semibold text-ink">자기소개를 길게 써 주세요.</b> 같은 사진 평가를 받은 사람끼리 비교해도, 자기소개를 100자 넘게 쓴
          사람은 안 쓴 사람보다 매칭이 몇 배 많았어요. 요즘 빠져 있는 것, 주말에 하는 일처럼 대화를 걸기 쉬운 이야기가 좋아요.
        </li>
        <li>
          📸 <b className="font-semibold text-ink">사진은 &lsquo;인스타 감성&rsquo; 사진이 평가가 잘 나와요.</b> 증명사진이나 셀카보다, 카페·여행지처럼 분위기가
          있는 곳에서 자연스럽게 찍힌 사진이 좋아요. 얼굴이 잘 보이는 밝은 사진이면 더 좋아요.
        </li>
        <li>
          🙂 <b className="font-semibold text-ink">관심사와 MBTI도 채워 주세요.</b> 공통점이 보이면 상대가 좋아요를 누르기 쉬워져요.
        </li>
      </ul>

      <div className="mt-6 space-y-2">
        <Button
          className="w-full"
          onClick={() => {
            close();
            router.push("/profile");
          }}
        >
          프로필 고치러 가기
        </Button>
        <Button variant="secondary" className="w-full" onClick={close}>
          닫기
        </Button>
      </div>
      <p className="mt-3 text-center text-[12px] text-ink-faint">이 안내는 알림 목록에서 다시 볼 수 있어요.</p>
    </Modal>
  );
}
