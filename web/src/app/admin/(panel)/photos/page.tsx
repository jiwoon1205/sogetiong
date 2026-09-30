"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageTitle, Spinner } from "@/components/ui";
import { adminApi } from "@/lib/admin";
import { cn, timeAgo } from "@/lib/format";

type PhotoItem = {
  photo_id: string;
  photo_count?: number; // 함께 제출한 사진 수 (최대 3)
  subject_code: string;
  review_status: string;
  uploaded_at: string;
  reviewed_at: string | null;
};

// "대기"에는 "확인 중"(누가 열어봤지만 평가를 안 끝낸 사진)도 함께 나온다
const TABS = [
  { value: "PENDING", label: "대기" },
  { value: "APPROVED", label: "승인" },
  { value: "REJECTED", label: "반려" },
];

export default function PhotoQueue() {
  const [status, setStatus] = useState("PENDING");
  const [items, setItems] = useState<PhotoItem[] | null>(null);

  useEffect(() => {
    setItems(null);
    adminApi<{ photos: PhotoItem[] }>(`/photo-reviews?status=${status}`).then((r) => setItems(r.photos));
  }, [status]);

  return (
    <>
      <PageTitle eyebrow="사진 검수" title="검수 대기열" desc="먼저 올라온 순서대로 보여요. 열어보고 평가를 안 끝낸 사진도 여기 남아요. 정지된 사용자의 사진은 빠져요." />
      <div className="mb-6 flex gap-6 border-b border-line text-[14px]">
        {TABS.map((t) => (
          <button key={t.value} onClick={() => setStatus(t.value)} className={status === t.value ? "-mb-px border-b-2 border-ink pb-3 font-semibold" : "pb-3 text-ink-faint hover:text-ink"}>
            {t.label}
          </button>
        ))}
      </div>
      {!items ? (
        <Spinner />
      ) : items.length === 0 ? (
        <p className="py-12 text-center text-[14px] text-ink-faint">비어 있어요.</p>
      ) : (
        <ul className="divide-y divide-line rounded-card border border-line bg-paper-card">
          {items.map((p, i) => (
            <li key={p.photo_id}>
              <Link href={`/admin/photos/${p.photo_id}`} className="grid grid-cols-[2.5rem_1fr_auto] items-center gap-4 px-5 py-4 hover:bg-paper-deep/60">
                <span className="num text-[13px] text-ink-faint">{String(i + 1).padStart(2, "0")}</span>
                <span>
                  <span className="font-mono text-[14.5px] font-semibold tracking-wide">{p.subject_code}</span>
                  <span className="ml-3 text-[13px] text-ink-faint">{timeAgo(p.uploaded_at)} 제출</span>
                  {(p.photo_count ?? 1) > 1 && (
                    <span className="ml-2 text-[12.5px] text-ink-soft">
                      사진 <span className="num">{p.photo_count}</span>장
                    </span>
                  )}
                  {p.review_status === "IN_REVIEW" && <span className="ml-2 rounded bg-paper-deep px-1.5 py-0.5 text-[11.5px] text-ink-soft">확인 중</span>}
                </span>
                <span className={cn("text-[13px]", status === "PENDING" ? "text-brick" : "text-ink-soft")}>{status === "PENDING" ? "평가하기 →" : "보기 →"}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
