import { cn } from "@/lib/format";

/** 단계 표시: 가는 선 + 현재 단계 이름 */
export function Steps({ labels, current, className }: { labels: string[]; current: number; className?: string }) {
  return (
    <div className={className}>
      <div className="flex gap-1.5" aria-hidden>
        {labels.map((_, i) => (
          <span key={i} className={cn("h-[3px] flex-1 rounded-full transition-colors", i <= current ? "bg-ink" : "bg-line")} />
        ))}
      </div>
      <p className="mt-3 text-[12.5px] text-ink-faint">
        <span className="num font-semibold text-ink">
          {current + 1}/{labels.length}
        </span>
        <span className="mx-2">·</span>
        {labels[current]}
      </p>
    </div>
  );
}
