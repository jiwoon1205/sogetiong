import { ScoreRow } from "@/components/ui";
import { SCORE_LABELS, type Card } from "@/lib/types";
import { cn } from "@/lib/format";

/** 다른 사용자에게 보이는 공개 카드. 사진 대신 글과 외적 평가로 사람을 소개한다. */
export function ProfileCard({ card, className, compact }: { card: Card; className?: string; compact?: boolean }) {
  const meta = [card.age ? `${card.age}세` : null, card.campus].filter(Boolean).join(" · ");
  return (
    <article className={cn("rounded-card border border-line bg-paper-card", className)}>
      <div className="border-b border-line px-6 pb-5 pt-6">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h2 className="truncate font-serif text-[24px] font-semibold leading-tight">{card.nickname}</h2>
            <p className="mt-1.5 text-[14px] text-ink-soft">{meta}</p>
          </div>
          {card.mbti && (
            <span className="shrink-0 rounded-sm border border-line-strong px-2 py-0.5 text-[12px] font-semibold tracking-wider text-ink-soft">
              {card.mbti}
            </span>
          )}
        </div>
        {card.department && <p className="mt-3 text-[14px] text-ink">{card.department}</p>}
      </div>

      {card.appearance && (
        <section className="space-y-2.5 border-b border-line px-6 py-5">
          <p className="eyebrow mb-3">외적 특징 · 운영진 평가</p>
          {SCORE_LABELS.map((s) => (
            <ScoreRow key={s.key} label={s.label} value={card.appearance![s.key]} />
          ))}
        </section>
      )}

      <div className={cn("space-y-5 px-6 py-5", compact && "space-y-4")}>
        {card.bio && (
          <section>
            <p className="eyebrow mb-2">소개</p>
            <p className="whitespace-pre-line text-[15px] leading-relaxed text-ink">{card.bio}</p>
          </section>
        )}
        {card.ideal_type && !compact && (
          <section>
            <p className="eyebrow mb-2">이상형</p>
            <p className="whitespace-pre-line text-[15px] leading-relaxed text-ink">{card.ideal_type}</p>
          </section>
        )}
        {card.interests.length > 0 && (
          <section>
            <p className="eyebrow mb-2">관심사</p>
            <p className="text-[14.5px] leading-relaxed text-ink-soft">{card.interests.join("  ·  ")}</p>
          </section>
        )}
        {!card.bio && !card.interests.length && !card.ideal_type && (
          <p className="text-[14px] text-ink-faint">아직 소개를 작성하지 않았어요.</p>
        )}
      </div>
    </article>
  );
}
