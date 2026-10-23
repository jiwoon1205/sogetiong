"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageTitle, Spinner } from "@/components/ui";
import GenderPie from "@/components/GenderPie";
import { adminApi, useAdmin } from "@/lib/admin";

type Stats = {
  users_total: number;
  users_active: number;
  users_active_today: number;
  users_normal: number;
  users_male: number;
  users_female: number;
  users_active_male: number;
  users_active_female: number;
  users_suspended: number;
  users_deleted?: number;
  users_deleted_recent?: number;
  photos_pending: number;
  matches_total: number;
  reports_open: number;
  payments_pending?: number;
  members_active?: number;
  members_vip?: number;
  members_expiring_week?: number;
  /** 학교별 숫자 (2026-10-24 경희대 확장). open = OPEN_SCHOOLS로 열려 있는지 */
  schools?: {
    name: string;
    email_domain: string;
    open: boolean;
    users_total: number;
    users_active: number;
    users_active_male: number;
    users_active_female: number;
  }[];
};

type NumberKey = { [K in keyof Stats]-?: Stats[K] extends number | undefined ? K : never }[keyof Stats];
type Tile = { key: NumberKey; label: string; hint?: string | ((s: Stats) => string); href?: string; urgent?: boolean; perm?: string };

const TILES: Tile[] = [
  { key: "photos_pending", label: "사진 검수 대기", href: "/admin/photos", urgent: true },
  { key: "reports_open", label: "처리할 신고", href: "/admin/reports", urgent: true },
  // 가입비 입금 확인 (2026-10-03). 통장을 보는 최고 관리자에게만 보인다
  { key: "payments_pending", label: "입금 확인 대기", hint: "15분 이내 확인", href: "/admin/payments", urgent: true, perm: "payments:confirm" },
  // 이용권 (2026-10-04 구독제). 유료화를 켜기 전에는 0
  {
    key: "members_active",
    label: "이용권 이용 중",
    hint: (s) => `VIP ${(s.members_vip ?? 0).toLocaleString()}명 · 7일 안에 끝남 ${(s.members_expiring_week ?? 0).toLocaleString()}명`,
    href: "/admin/users?membership=active",
    perm: "payments:confirm",
  },
  { key: "users_active", label: "활성 사용자", hint: "사진 검수 완료 + 최근 7일 접속" },
  { key: "users_active_today", label: "오늘 접속" },
  { key: "users_total", label: "전체 가입자", hint: "탈퇴·정지 포함" },
  { key: "users_male", label: "남자", hint: "정상 계정", href: "/admin/users?gender=MALE" },
  { key: "users_female", label: "여자", hint: "정상 계정", href: "/admin/users?gender=FEMALE" },
  { key: "matches_total", label: "누적 매칭" },
  { key: "users_suspended", label: "정지된 계정" },
  {
    key: "users_deleted",
    label: "탈퇴한 사용자",
    // 탈퇴 후 7일 동안은 프로필·사진을 볼 수 있고, 그 뒤 자동 삭제된다
    hint: (s) => `최근 7일 ${(s.users_deleted_recent ?? 0).toLocaleString()}명 · 이 사람들은 정보 열람 가능`,
    href: "/admin/users?status=DELETED",
  },
];

// 성비: 남자 : 여자 = 1 : x
function genderRatio(s: Stats): string | null {
  if (!s.users_male || !s.users_female) return null;
  return `남 1 : 여 ${(s.users_female / s.users_male).toFixed(2)}`;
}

export default function AdminDashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const admin = useAdmin();
  const tiles = TILES.filter((t) => !t.perm || admin.can(t.perm));
  // 넓은 화면(3칸)에서 마지막 줄이 비면 회색 칸이 보이므로 빈 칸을 채운다
  const lgFillers = (3 - (tiles.length % 3)) % 3;

  useEffect(() => {
    adminApi<Stats>("/dashboard").then(setStats);
  }, []);

  if (!stats) return <Spinner />;

  return (
    <>
      <PageTitle eyebrow="현황" title="오늘의 운영" desc="개인정보 없이 숫자만 보여줍니다." />
      <div className="mb-4 flex flex-wrap items-center gap-x-6 gap-y-3">
        <GenderPie male={stats.users_active_male ?? 0} female={stats.users_active_female ?? 0} />
        {genderRatio(stats) && <p className="text-[14px] text-ink-soft">전체 성비 {genderRatio(stats)}</p>}
      </div>
      <div className="grid grid-cols-2 gap-px overflow-hidden rounded-card border border-line bg-line lg:grid-cols-3">
        {tiles.map((t) => {
          const value = stats[t.key] ?? 0;
          const hint = typeof t.hint === "function" ? t.hint(stats) : t.hint;
          const body = (
            <div className="h-full bg-paper-card p-6">
              <p className="text-[13px] text-ink-soft">{t.label}</p>
              <p className={`num mt-3 font-serif text-[34px] font-semibold leading-none ${t.urgent && value > 0 ? "text-brick" : "text-ink"}`}>{value.toLocaleString()}</p>
              {hint && <p className="mt-2 text-[12px] text-ink-faint">{hint}</p>}
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
        {Array.from({ length: lgFillers }, (_, i) => (
          <div key={`filler-${i}`} className="hidden bg-paper-card lg:block" aria-hidden />
        ))}
      </div>
      {(stats.schools?.length ?? 0) > 1 && <SchoolTable schools={stats.schools!} />}
    </>
  );
}

/** 학교별 숫자 (2026-10-24). 학교가 둘 이상 있을 때만 보인다. 닫힌 학교 = 아직 가입 불가 (설정 OPEN_SCHOOLS) */
function SchoolTable({ schools }: { schools: NonNullable<Stats["schools"]> }) {
  return (
    <section className="mt-8">
      <h2 className="mb-3 text-[14px] font-medium text-ink-soft">학교별</h2>
      <div className="overflow-x-auto rounded-card border border-line bg-paper-card">
        <table className="w-full min-w-[34rem] text-[14px]">
          <thead className="border-b border-line text-left text-[12.5px] text-ink-faint">
            <tr>
              <th className="px-5 py-3 font-normal">학교</th>
              <th className="px-5 py-3 font-normal">상태</th>
              <th className="px-5 py-3 text-right font-normal">전체 가입자</th>
              <th className="px-5 py-3 text-right font-normal">활성 사용자</th>
              <th className="px-5 py-3 font-normal">활성 성비</th>
            </tr>
          </thead>
          <tbody>
            {schools.map((sc) => (
              <tr key={sc.email_domain} className="border-b border-line last:border-0">
                <td className="px-5 py-3">
                  <Link href={`/admin/users?school=${encodeURIComponent(sc.email_domain)}`} className="underline-offset-4 hover:underline">
                    {sc.name}
                  </Link>
                  <span className="ml-2 text-[12px] text-ink-faint">@{sc.email_domain}</span>
                </td>
                <td className="px-5 py-3">{sc.open ? "열림" : <span className="text-ink-faint">닫힘 (가입 불가)</span>}</td>
                <td className="num px-5 py-3 text-right">{sc.users_total.toLocaleString()}</td>
                <td className="num px-5 py-3 text-right">{sc.users_active.toLocaleString()}</td>
                <td className="num px-5 py-3 text-ink-soft">
                  남 {sc.users_active_male.toLocaleString()} · 여 {sc.users_active_female.toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
