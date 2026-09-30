import Link from "next/link";

/** 워드마크. 로고 이미지 대신 세리프 글자 + 작은 점 하나. */
export function Brand({ href = "/", sub }: { href?: string; sub?: string }) {
  return (
    <Link href={href} className="group inline-flex items-baseline gap-2">
      <span className="font-serif text-[19px] font-semibold tracking-tight text-ink">훕팅</span>
      <span className="h-1.5 w-1.5 translate-y-[-2px] rounded-full bg-brick" aria-hidden />
      {sub && <span className="text-[12px] font-medium text-ink-faint">{sub}</span>}
    </Link>
  );
}
