"use client";

import { useEffect } from "react";
import { Button, ButtonLink } from "@/components/ui";

/** 서로 좋아요(매칭)가 됐을 때 보여주는 축하 화면 (2026-09-30).
 *
 *  - 두 사람의 동그라미(닉네임 첫 글자)가 양쪽에서 다가와 만나고, 가운데에서 하트가 톡 터진다
 *  - 작은 하트 조각들이 위로 흩어지며 사라진다
 *  - 휴대폰이면 짧게 진동 (지원하는 기기만)
 *  - "움직임 줄이기"를 켠 사용자에게는 애니메이션 없이 조용히 보여준다
 *  사진은 쓰지 않는다 (사진은 다른 학생에게 절대 보이지 않음).
 */
export function MatchCelebration({
  partnerName,
  matchId,
  onClose,
}: {
  partnerName: string;
  matchId: string;
  onClose: () => void;
}) {
  useEffect(() => {
    // 짧게 두 번 진동 (지원 안 하는 브라우저는 그냥 넘어감)
    try {
      if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) navigator.vibrate?.([40, 60, 40]);
    } catch {}
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    // 뒤 화면이 스크롤되지 않게
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose]);

  return (
    <div role="dialog" aria-modal="true" aria-label={`${partnerName}님과 매칭됐어요`} className="mc-backdrop fixed inset-0 z-50 flex items-center justify-center overflow-hidden bg-paper/95 px-6 backdrop-blur-[2px]">
      {/* 흩어지는 하트 조각 */}
      <div aria-hidden className="pointer-events-none absolute inset-0">
        {PARTICLES.map((p, i) => (
          <span
            key={i}
            className="mc-particle absolute left-1/2 top-[38%] text-brick"
            style={
              {
                "--dx": `${p.dx}px`,
                "--dy": `${p.dy}px`,
                "--rot": `${p.rot}deg`,
                animationDelay: `${420 + p.delay}ms`,
                fontSize: p.size,
                opacity: 0,
              } as React.CSSProperties
            }
          >
            ♥
          </span>
        ))}
      </div>

      <div className="relative w-full max-w-sm text-center">
        {/* 두 사람이 만나는 장면 */}
        <div aria-hidden className="relative mx-auto mb-9 flex h-24 items-center justify-center">
          <span className="mc-left flex h-[72px] w-[72px] items-center justify-center rounded-full border border-line-strong bg-paper-card font-serif text-[26px] font-semibold text-ink-soft shadow-[0_2px_10px_rgba(30,29,27,0.08)]">
            나
          </span>
          <span className="mc-heart relative z-10 -mx-3 flex h-11 w-11 items-center justify-center rounded-full bg-brick text-[20px] text-paper shadow-[0_4px_14px_rgba(142,59,43,0.35)]">
            ♥
            <span className="mc-ring absolute inset-0 rounded-full border-2 border-brick" />
          </span>
          <span className="mc-right flex h-[72px] w-[72px] items-center justify-center rounded-full border border-line-strong bg-paper-card font-serif text-[26px] font-semibold text-ink-soft shadow-[0_2px_10px_rgba(30,29,27,0.08)]">
            {partnerName.slice(0, 1)}
          </span>
        </div>

        <div className="mc-text">
          <p className="eyebrow mb-4 text-brick">서로 좋아요</p>
          <h2 className="font-serif text-[30px] font-semibold leading-snug">
            {partnerName}님과
            <br />
            마음이 맞았어요
          </h2>
          <p className="mt-4 text-[14.5px] leading-relaxed text-ink-soft">이름도 얼굴도 모르는 채로, 대화부터 시작해보세요.</p>
        </div>
        <div className="mc-actions mt-8 space-y-3">
          <ButtonLink href={`/chat/${matchId}`} size="lg" className="w-full">
            대화 시작하기
          </ButtonLink>
          <Button variant="ghost" className="w-full" onClick={onClose}>
            계속 둘러보기
          </Button>
        </div>
      </div>

      <style>{CSS}</style>
    </div>
  );
}

// 하트 조각: 가운데에서 사방(주로 위쪽)으로 퍼진다. 매번 같은 모양이 나오게 고정값으로 둔다.
const PARTICLES = [
  { dx: -150, dy: -170, rot: -30, size: 16, delay: 0 },
  { dx: -95, dy: -230, rot: -12, size: 12, delay: 60 },
  { dx: -40, dy: -260, rot: 8, size: 18, delay: 20 },
  { dx: 30, dy: -250, rot: -6, size: 13, delay: 90 },
  { dx: 90, dy: -215, rot: 18, size: 17, delay: 30 },
  { dx: 150, dy: -160, rot: 28, size: 12, delay: 70 },
  { dx: -175, dy: -60, rot: -40, size: 11, delay: 120 },
  { dx: 175, dy: -70, rot: 40, size: 14, delay: 110 },
  { dx: -120, dy: 40, rot: -20, size: 10, delay: 150 },
  { dx: 125, dy: 30, rot: 22, size: 11, delay: 160 },
  { dx: -10, dy: -150, rot: 0, size: 10, delay: 180 },
  { dx: 60, dy: -120, rot: 14, size: 9, delay: 200 },
];

const CSS = `
.mc-backdrop { animation: mc-fade 260ms ease-out both; }
.mc-left  { animation: mc-in-left 520ms cubic-bezier(.2,.9,.25,1.15) both; }
.mc-right { animation: mc-in-right 520ms cubic-bezier(.2,.9,.25,1.15) both; }
.mc-heart { animation: mc-pop 460ms cubic-bezier(.3,1.6,.5,1) 380ms both; }
.mc-ring  { animation: mc-ring 900ms ease-out 520ms both; }
.mc-text    { animation: mc-rise 480ms ease-out 560ms both; }
.mc-actions { animation: mc-rise 480ms ease-out 720ms both; }
.mc-particle { animation: mc-burst 1300ms cubic-bezier(.15,.7,.3,1) both; }

@keyframes mc-fade { from { opacity: 0 } to { opacity: 1 } }
@keyframes mc-in-left  { from { transform: translateX(-90px) scale(.85); opacity: 0 } to { transform: none; opacity: 1 } }
@keyframes mc-in-right { from { transform: translateX(90px) scale(.85);  opacity: 0 } to { transform: none; opacity: 1 } }
@keyframes mc-pop { 0% { transform: scale(0); opacity: 0 } 70% { transform: scale(1.25); opacity: 1 } 100% { transform: scale(1) } }
@keyframes mc-ring { 0% { transform: scale(1); opacity: .7 } 100% { transform: scale(2.6); opacity: 0 } }
@keyframes mc-rise { from { transform: translateY(12px); opacity: 0 } to { transform: none; opacity: 1 } }
@keyframes mc-burst {
  0%   { transform: translate(-50%, -50%) scale(.4) rotate(0deg); opacity: 0 }
  15%  { opacity: 1 }
  100% { transform: translate(calc(-50% + var(--dx)), calc(-50% + var(--dy))) scale(1) rotate(var(--rot)); opacity: 0 }
}
@media (prefers-reduced-motion: reduce) {
  .mc-backdrop, .mc-left, .mc-right, .mc-heart, .mc-text, .mc-actions { animation: none !important; }
  .mc-ring, .mc-particle { display: none; }
}
`;
