"use client";

import { useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useState } from "react";
import { ApiError, api } from "@/lib/api";

export type AdminMe = { email: string; role: string; permissions: string[] };
const AdminContext = createContext<AdminMe | null>(null);

/** 관리자 화면 보호: 로그인 + 2단계 인증이 끝나지 않았으면 /admin/login 으로 */
export function AdminGate({ children, fallback }: { children: React.ReactNode; fallback: React.ReactNode }) {
  const router = useRouter();
  const [me, setMe] = useState<AdminMe | null>(null);

  useEffect(() => {
    api<AdminMe>("/admin/me", { admin: true })
      .then(setMe)
      .catch((err) => {
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) router.replace("/admin/login");
      });
  }, [router]);

  if (!me) return <>{fallback}</>;
  return <AdminContext.Provider value={me}>{children}</AdminContext.Provider>;
}

export function useAdmin(): AdminMe & { can: (p: string) => boolean } {
  const me = useContext(AdminContext);
  if (!me) throw new Error("useAdmin must be used inside AdminGate");
  return { ...me, can: (p) => me.permissions.includes(p) };
}

/** 관리자 API 호출 (admin CSRF 쿠키 사용) */
export function adminApi<T = unknown>(path: string, opts: Parameters<typeof api>[1] = {}) {
  return api<T>(`/admin${path}`, { ...opts, admin: true });
}

export const ROLE_LABEL: Record<string, string> = {
  SUPER_ADMIN: "최고 관리자",
  MODERATOR: "신고·제재 담당",
  PHOTO_REVIEWER: "사진 검수 담당",
};

export const USER_STATUS_LABEL: Record<string, string> = {
  ACTIVE: "정상",
  SUSPENDED: "일시 정지",
  BANNED: "영구 정지",
  DELETED: "탈퇴",
};

export const REPORT_STATUS_LABEL: Record<string, string> = {
  OPEN: "접수",
  IN_REVIEW: "검토 중",
  RESOLVED: "처리 완료",
  DISMISSED: "기각",
};
