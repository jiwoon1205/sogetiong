"use client";

import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { SurveyScreen } from "@/components/SurveyScreen";
import { ApiError, api } from "@/lib/api";
import type { Me } from "@/lib/types";

type SessionValue = { me: Me; refresh: () => Promise<void> };
const SessionContext = createContext<SessionValue | null>(null);

/** 로그인한 사용자만 볼 수 있는 화면을 감싼다. 로그인이 안 돼 있으면 /login 으로 보낸다.
 *  설문을 받는 중이고 아직 안 답한 사람에게는 설문 화면을 먼저 보여준다. */
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
  // 설문 (2026-10-05): 관리자가 설문을 켰고 아직 안 답했으면, 로그인·가입 직후 어떤 화면이든 설문부터 (꼭 답해야 넘어감)
  if (me.survey?.pending) return <SurveyScreen onDone={refresh} />;
  return <SessionContext.Provider value={{ me, refresh }}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession must be used inside SessionGate");
  return value;
}
