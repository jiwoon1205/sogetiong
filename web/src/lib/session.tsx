"use client";

import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { ApiError, api } from "@/lib/api";
import type { Me } from "@/lib/types";

type SessionValue = { me: Me; refresh: () => Promise<void> };
const SessionContext = createContext<SessionValue | null>(null);

/** 로그인한 사용자만 볼 수 있는 화면을 감싼다. 로그인이 안 돼 있으면 /login 으로 보낸다. */
export function SessionGate({ children, fallback }: { children: React.ReactNode; fallback: React.ReactNode }) {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);

  const refresh = useCallback(async () => {
    try {
      setMe(await api<Me>("/me"));
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) router.replace("/login");
    }
  }, [router]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  if (!me) return <>{fallback}</>;
  return <SessionContext.Provider value={{ me, refresh }}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession must be used inside SessionGate");
  return value;
}
