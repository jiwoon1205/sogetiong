"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Brand } from "@/components/Brand";
import { Spinner } from "@/components/ui";
import { AdminGate, ROLE_LABEL, adminApi, useAdmin } from "@/lib/admin";
import { cn } from "@/lib/format";

const NAV = [
  { href: "/admin", label: "현황", perm: "dashboard:read" },
  { href: "/admin/photos", label: "사진 검수", perm: "photos:read" },
  { href: "/admin/payments", label: "입금 확인", perm: "payments:confirm" },
  { href: "/admin/reports", label: "신고", perm: "reports:read" },
  { href: "/admin/chats", label: "대화", perm: "chats:read" },
  { href: "/admin/users", label: "사용자", perm: "users:read" },
  { href: "/admin/match-suspensions", label: "매칭 정지된 사용자", perm: "users:status" },
  { href: "/admin/audit-logs", label: "감사 로그", perm: "audit:read" },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <AdminGate fallback={<Spinner />}>
      <Shell>{children}</Shell>
    </AdminGate>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const admin = useAdmin();

  async function logout() {
    await adminApi("/auth/logout", { method: "POST" }).catch(() => {});
    router.replace("/admin/login");
  }

  const isActive = (href: string) => (href === "/admin" ? path === "/admin" : path.startsWith(href));

  return (
    <div className="min-h-dvh md:grid md:grid-cols-[13.5rem_1fr]">
      <aside className="border-b border-line bg-paper-deep md:sticky md:top-0 md:h-dvh md:border-b-0 md:border-r">
        <div className="flex items-center justify-between px-5 py-5 md:block">
          <Brand href="/admin" sub="운영" />
          <div className="md:mt-6">
            <p className="hidden text-[12.5px] text-ink-soft md:block">{admin.email}</p>
            <p className="text-[12px] text-ink-faint">{ROLE_LABEL[admin.role] ?? admin.role}</p>
          </div>
        </div>
        <nav className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-col md:px-3">
          {NAV.filter((n) => admin.can(n.perm)).map((n) => (
            <Link
              key={n.href}
              href={n.href}
              className={cn(
                "whitespace-nowrap rounded-md px-3 py-2 text-[14px] transition-colors",
                isActive(n.href) ? "bg-paper font-semibold text-ink" : "text-ink-soft hover:text-ink",
              )}
            >
              {n.label}
            </Link>
          ))}
          <button onClick={logout} className="whitespace-nowrap rounded-md px-3 py-2 text-left text-[14px] text-ink-faint hover:text-ink md:mt-4">
            로그아웃
          </button>
        </nav>
      </aside>
      <main className="px-5 py-8 md:px-10 md:py-10">
        <div className="mx-auto max-w-5xl">{children}</div>
      </main>
    </div>
  );
}
