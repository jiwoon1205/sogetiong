"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageTitle, Spinner } from "@/components/ui";
import { adminApi } from "@/lib/admin";

type Stats = {
  users_total: number;
  users_active: number;
  users_active_today: number;
  users_normal: number;
  users_male: number;
  users_female: number;
  users_suspended: number;
  photos_pending: number;
  matches_total: number;
  reports_open: number;
};

const TILES: { key: keyof Stats; label: string; hint?: string; href?: string; urgent?: boolean }[] = [
  { key: "photos_pending", label: "사진 검수 대기", href: "/admin/photos", urgent: true },
  { key: "reports_open", label: "처리할 신고", href: "/admin/reports", urgent: true },
  { key: "users_active", label: "활성 사용자", hint: "최근 7일 안에 접속" },
  { key: "users_active_today", label: "오늘 접속" },
  { key: "users_total", label: "전체 가입자", hint: "탈퇴·정지 포함" },
  { key: "users_male", label: "남자", hint: "정상 계정", href: "/admin/users?gender=MALE" },
  { key: "users_female", label: "여자", hint: "정상 계정", href: "/admin/users?gender=FEMALE" },
  { key: "matches_total", label: "누적 매칭" },
  { key: "users_suspended", label: "정지된 계정" },
];

// 성비: 남자 : 여자 = 1 : x
function genderRatio(s: Stats): string | null {
  if (!s.users_male || !s.users_female) return null;
  return `남 1 : 여 ${(s.users_female / s.users_male).toFixed(2)}`;
}

export default function AdminDashboard() {
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    adminApi<Stats>("/dashboard").then(setStats);
  }, []);

  if (!stats) return <Spinner />;

  return (
    <>
      <PageTitle eyebrow="현황" title="오늘의 운영" desc="개인정보 없이 숫자만 보여줍니다." />
      {genderRatio(stats) && <p className="mb-4 text-[14px] text-ink-soft">성비 {genderRatio(stats)}</p>}
      <div className="grid grid-cols-2 gap-px overflow-hidden rounded-card border border-line bg-line lg:grid-cols-3">
        {TILES.map((t) => {
          const value = stats[t.key];
          const body = (
            <div className="h-full bg-paper-card p-6">
              <p className="text-[13px] text-ink-soft">{t.label}</p>
              <p className={`num mt-3 font-serif text-[34px] font-semibold leading-none ${t.urgent && value > 0 ? "text-brick" : "text-ink"}`}>{value.toLocaleString()}</p>
              {t.hint && <p className="mt-2 text-[12px] text-ink-faint">{t.hint}</p>}
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
