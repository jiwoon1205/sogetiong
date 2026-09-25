"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageTitle, Spinner } from "@/components/ui";
import { adminApi } from "@/lib/admin";

type Stats = {
  users_total: number;
  users_active: number;
  users_suspended: number;
  photos_pending: number;
  matches_total: number;
  reports_open: number;
};

const TILES: { key: keyof Stats; label: string; href?: string; urgent?: boolean }[] = [
  { key: "photos_pending", label: "사진 검수 대기", href: "/admin/photos", urgent: true },
  { key: "reports_open", label: "처리할 신고", href: "/admin/reports", urgent: true },
  { key: "users_active", label: "활성 사용자" },
  { key: "users_total", label: "전체 가입자" },
  { key: "matches_total", label: "누적 매칭" },
  { key: "users_suspended", label: "정지된 계정" },
];

export default function AdminDashboard() {
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    adminApi<Stats>("/dashboard").then(setStats);
  }, []);

  if (!stats) return <Spinner />;

  return (
    <>
      <PageTitle eyebrow="현황" title="오늘의 운영" desc="개인정보 없이 숫자만 보여줍니다." />
      <div className="grid grid-cols-2 gap-px overflow-hidden rounded-card border border-line bg-line lg:grid-cols-3">
        {TILES.map((t) => {
          const value = stats[t.key];
          const body = (
            <div className="h-full bg-paper-card p-6">
              <p className="text-[13px] text-ink-soft">{t.label}</p>
              <p className={`num mt-3 font-serif text-[34px] font-semibold leading-none ${t.urgent && value > 0 ? "text-brick" : "text-ink"}`}>{value.toLocaleString()}</p>
              {t.href && <p className="mt-4 text-[12.5px] text-ink-faint">바로가기 →</p>}
            </div>
          );
          return t.href ? (
            <Link key={t.key} href={t.href} className="block hover:opacity-90">
              {body}
            </Link>
          ) : (
            <div key={t.key}>{body}</div>
          );
        })}
      </div>
    </>
  );
}
