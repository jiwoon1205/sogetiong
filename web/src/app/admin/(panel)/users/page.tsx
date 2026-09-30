"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Input, PageTitle, Select, Spinner } from "@/components/ui";
import { USER_STATUS_LABEL, adminApi } from "@/lib/admin";
import { cn, dateTime } from "@/lib/format";

type UserRow = {
  user_id: string;
  subject_code: string;
  nickname: string | null;
  status: string;
  onboarding_stage?: string;
  reports_received: number;
  created_at: string;
};

// 가입 후 어느 단계까지 했는지 (어디서 멈췄는지 보려고)
const STAGE_LABEL: Record<string, string> = {
  PROFILE: "프로필 미완료",
  PREFERENCES: "매칭 조건 미설정",
  PHOTO: "사진 미제출",
  REVIEW: "사진 검수 대기",
  DONE: "완료",
};

export default function UsersPage() {
  const [items, setItems] = useState<UserRow[] | null>(null);
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");

  useEffect(() => {
    const t = setTimeout(() => {
      const params = new URLSearchParams();
      if (status) params.set("status", status);
      if (q.trim()) params.set("nickname", q.trim());
      adminApi<{ users: UserRow[] }>(`/users?${params}`).then((r) => setItems(r.users));
    }, 250);
    return () => clearTimeout(t);
  }, [status, q]);

  return (
    <>
      <PageTitle eyebrow="사용자" title="사용자 관리" desc="실명·이메일 등 개인정보는 목록에 나오지 않아요." />
      <div className="mb-5 grid gap-3 sm:grid-cols-[1fr_11rem]">
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="닉네임으로 찾기" />
        <Select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">모든 상태</option>
          {Object.entries(USER_STATUS_LABEL).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </Select>
      </div>
      {!items ? (
        <Spinner />
      ) : (
        <div className="overflow-x-auto rounded-card border border-line bg-paper-card">
          <table className="w-full min-w-[44rem] text-[14px]">
            <thead className="border-b border-line text-left text-[12.5px] text-ink-faint">
              <tr>
                <th className="px-5 py-3 font-normal">코드</th>
                <th className="px-5 py-3 font-normal">닉네임</th>
                <th className="px-5 py-3 font-normal">상태</th>
                <th className="px-5 py-3 font-normal">가입 단계</th>
                <th className="px-5 py-3 text-right font-normal">받은 신고</th>
                <th className="px-5 py-3 font-normal">가입</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {items.map((u) => (
                <tr key={u.user_id} className="hover:bg-paper-deep/60">
                  <td className="px-5 py-3">
                    <Link href={`/admin/users/${u.user_id}`} className="font-mono font-semibold underline-offset-4 hover:underline">
                      {u.subject_code}
                    </Link>
                  </td>
                  <td className="px-5 py-3">{u.nickname ?? <span className="text-ink-faint">—</span>}</td>
                  <td className={cn("px-5 py-3", u.status !== "ACTIVE" && "text-brick")}>{USER_STATUS_LABEL[u.status] ?? u.status}</td>
                  <td className={cn("px-5 py-3", u.onboarding_stage === "DONE" ? "text-ink-soft" : "text-brick")}>
                    {u.onboarding_stage ? STAGE_LABEL[u.onboarding_stage] ?? u.onboarding_stage : "—"}
                  </td>
                  <td className={cn("num px-5 py-3 text-right", u.reports_received > 0 && "font-semibold text-brick")}>{u.reports_received}</td>
                  <td className="px-5 py-3 text-ink-soft">{dateTime(u.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {items.length === 0 && <p className="py-10 text-center text-[14px] text-ink-faint">결과가 없어요.</p>}
        </div>
      )}
    </>
  );
}
