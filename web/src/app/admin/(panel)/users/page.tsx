"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { Input, PageTitle, Select, Spinner } from "@/components/ui";
import { USER_STATUS_LABEL, adminApi } from "@/lib/admin";
import { cn, dateTime, timeAgo } from "@/lib/format";

type UserRow = {
  user_id: string;
  subject_code: string;
  nickname: string | null;
  gender: string | null;
  status: string;
  onboarding_stage?: string;
  reports_received: number;
  last_active_at: string | null;
  created_at: string;
  member_until?: string | null;
  vip_until?: string | null;
};

// 이용권 필터 (현황의 "이용권 이용 중" 칸을 누르면 ?membership=active 로 들어온다)
const MEMBERSHIP_LABEL: Record<string, string> = { active: "이용권 이용 중", vip: "VIP 이용 중", expiring: "7일 안에 끝남" };

// 가입 후 어느 단계까지 했는지 (어디서 멈췄는지 보려고)
const STAGE_LABEL: Record<string, string> = {
  PROFILE: "프로필 미완료",
  PREFERENCES: "매칭 조건 미설정",
  PAYMENT: "이용권 입금 전",
  PAYMENT_CHECK: "입금 확인 대기",
  PHOTO: "사진 미제출",
  REVIEW: "사진 검수 대기",
  DONE: "완료",
};

const GENDER_LABEL: Record<string, string> = { MALE: "남", FEMALE: "여" };

// useSearchParams는 Suspense 안에서만 쓸 수 있다 (Next.js 규칙)
export default function UsersPage() {
  return (
    <Suspense fallback={<Spinner />}>
      <UsersList />
    </Suspense>
  );
}

function UsersList() {
  const searchParams = useSearchParams();
  const [items, setItems] = useState<UserRow[] | null>(null);
  const [total, setTotal] = useState(0);
  // 대시보드의 "탈퇴한 사용자" 칸을 누르면 ?status=DELETED 로 들어온다
  const [status, setStatus] = useState(() => {
    const st = searchParams.get("status");
    return st && st in USER_STATUS_LABEL ? st : "";
  });
  // 대시보드의 "남자/여자" 칸을 누르면 ?gender=MALE 처럼 들어온다
  const [gender, setGender] = useState(() => {
    const g = searchParams.get("gender");
    return g === "MALE" || g === "FEMALE" ? g : "";
  });
  const [membership, setMembership] = useState(() => {
    const m = searchParams.get("membership");
    return m && m in MEMBERSHIP_LABEL ? m : "";
  });
  const [q, setQ] = useState("");

  useEffect(() => {
    const t = setTimeout(() => {
      const params = new URLSearchParams();
      if (status) params.set("status", status);
      if (gender) params.set("gender", gender);
      if (membership) params.set("membership", membership);
      if (q.trim()) params.set("q", q.trim());
      adminApi<{ users: UserRow[]; total?: number }>(`/users?${params}`).then((r) => {
        setItems(r.users);
        setTotal(r.total ?? r.users.length);
      });
    }, 250);
    return () => clearTimeout(t);
  }, [status, gender, membership, q]);

  return (
    <>
      <PageTitle eyebrow="사용자" title="사용자 관리" desc="실명·이메일 등 개인정보는 목록에 나오지 않아요." />
      <div className="mb-5 grid gap-3 sm:grid-cols-[1fr_8rem_11rem_10rem]">
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="닉네임 또는 코드로 찾기" />
        <Select value={gender} onChange={(e) => setGender(e.target.value)}>
          <option value="">모든 성별</option>
          <option value="MALE">남자</option>
          <option value="FEMALE">여자</option>
        </Select>
        <Select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">모든 상태</option>
          {Object.entries(USER_STATUS_LABEL).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </Select>
        <Select value={membership} onChange={(e) => setMembership(e.target.value)}>
          <option value="">모든 이용권</option>
          {Object.entries(MEMBERSHIP_LABEL).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </Select>
      </div>
      {items && (
        <p className="mb-2 text-[12.5px] text-ink-faint">
          {total > items.length ? `${total}명 중 최근 가입한 ${items.length}명` : `${total}명`}
        </p>
      )}
      {!items ? (
        <Spinner />
      ) : (
        <div className="overflow-x-auto rounded-card border border-line bg-paper-card">
          <table className="w-full min-w-[62rem] text-[14px]">
            <thead className="border-b border-line text-left text-[12.5px] text-ink-faint">
              <tr>
                <th className="px-5 py-3 font-normal">코드</th>
                <th className="px-5 py-3 font-normal">닉네임</th>
                <th className="px-5 py-3 font-normal">성별</th>
                <th className="px-5 py-3 font-normal">상태</th>
                <th className="px-5 py-3 font-normal">가입 단계</th>
                <th className="px-5 py-3 font-normal">이용권 끝</th>
                <th className="px-5 py-3 text-right font-normal">받은 신고</th>
                <th className="px-5 py-3 font-normal">마지막 접속</th>
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
                  <td className="px-5 py-3">{u.gender ? GENDER_LABEL[u.gender] ?? u.gender : <span className="text-ink-faint">—</span>}</td>
                  <td className={cn("px-5 py-3", u.status !== "ACTIVE" && "text-brick")}>{USER_STATUS_LABEL[u.status] ?? u.status}</td>
                  <td className={cn("px-5 py-3", u.onboarding_stage === "DONE" ? "text-ink-soft" : "text-brick")}>
                    {u.onboarding_stage ? STAGE_LABEL[u.onboarding_stage] ?? u.onboarding_stage : "—"}
                  </td>
                  <td className="px-5 py-3 text-ink-soft">{membershipEnd(u)}</td>
                  <td className={cn("num px-5 py-3 text-right", u.reports_received > 0 && "font-semibold text-brick")}>{u.reports_received}</td>
                  <td className="px-5 py-3 text-ink-soft" title={u.last_active_at ? dateTime(u.last_active_at) : undefined}>
                    {u.last_active_at ? timeAgo(u.last_active_at) : "—"}
                  </td>
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

// 이용권 끝나는 날 (VIP면 VIP 끝도 같이). 끝났거나 없으면 —
function membershipEnd(u: UserRow): string {
  const now = Date.now();
  const live = (t?: string | null) => (t && new Date(t).getTime() > now ? t : null);
  const member = live(u.member_until);
  const vip = live(u.vip_until);
  if (!member && !vip) return "—";
  const parts: string[] = [];
  if (member) parts.push(dateTime(member));
  if (vip) parts.push(`VIP ${dateTime(vip)}`);
  return parts.join(" · ");
}
