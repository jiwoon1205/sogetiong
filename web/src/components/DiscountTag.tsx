"use client";

import { dday, ddayEnd, discountPercent } from "@/lib/format";
import type { Membership } from "@/lib/types";

/** 할인 중인가: 지금 가격이 정가보다 싸고, 할인 마감 전 (2026-10-07) */
export function onSale(m: Membership | undefined | null): m is Membership & { regular_price: number } {
  return !!m && !!m.regular_price && m.price < m.regular_price && (!m.discount_until || dday(m.discount_until) !== null);
}

/** "할인 D-Day · 오늘 밤 12시 마감 · 62% 할인" 띠 (할인 중일 때만) */
export function DiscountTag({ m, className = "" }: { m: Membership | undefined | null; className?: string }) {
  if (!onSale(m)) return null;
  const d = m.discount_until ? dday(m.discount_until) : null;
  return (
    <span className={`inline-flex flex-wrap items-center gap-1.5 text-[12.5px] ${className}`}>
      {d && <span className="rounded-full bg-brick px-2 py-0.5 font-semibold text-paper">할인 {d}</span>}
      <span className="font-semibold text-brick">{discountPercent(m.regular_price, m.price)}% 할인</span>
      {m.discount_until && <span className="text-ink-soft">· {ddayEnd(m.discount_until)}</span>}
    </span>
  );
}

/** 정가에 가로줄 + 할인가. 할인 중이 아니면 지금 가격만 */
export function SalePrice({
  m,
  price,
  strikeClass = "text-ink-faint",
  priceClass = "",
}: {
  m: Membership | undefined | null;
  price?: number;
  strikeClass?: string;
  priceClass?: string;
}) {
  const now = price ?? m?.price ?? 0;
  if (!onSale(m) || now >= m.regular_price) return <>{now.toLocaleString()}원</>;
  return (
    <>
      <s className={strikeClass}>{m.regular_price.toLocaleString()}원</s> <b className={`font-semibold ${priceClass}`}>{now.toLocaleString()}원</b>
    </>
  );
}
