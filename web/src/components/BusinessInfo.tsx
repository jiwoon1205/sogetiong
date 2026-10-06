import { BUSINESS as B } from "@/lib/business";
import { cn } from "@/lib/format";

/** 사이트 아래쪽 사업자 정보 + 이용약관·개인정보처리방침 링크 (전자상거래법 제10조, 2026-10-06) */
export function BusinessInfo({ className }: { className?: string }) {
  const items = [
    `상호 ${B.name}`,
    `대표자 ${B.owner}`,
    `사업자등록번호 ${B.registrationNumber}`,
    `통신판매업 ${B.mailOrderNumber}`,
    `주소 ${B.address}`,
    `전화 ${B.phone}`,
    `이메일 ${B.email}`,
    `호스팅 ${B.hosting}`,
  ];
  return (
    <div className={cn("space-y-2 text-[12px] leading-relaxed text-ink-faint", className)}>
      <p className="flex gap-3">
        <a href="/terms" className="underline underline-offset-4">
          이용약관
        </a>
        {/* 개인정보처리방침은 다른 링크보다 눈에 띄게 (개인정보보호법 시행령 제31조) */}
        <a href="/privacy" className="font-semibold text-ink-soft underline underline-offset-4">
          개인정보처리방침
        </a>
      </p>
      <p>
        {items.map((t, i) => (
          <span key={t}>
            {i > 0 && <span aria-hidden> · </span>}
            {t}
          </span>
        ))}
      </p>
    </div>
  );
}
