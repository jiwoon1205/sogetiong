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

  // 휴대폰(특히 "홈 화면에 추가"한 앱)은 다시 열어도 페이지를 새로 불러오지 않고 멈춰 있던 화면을 그대로 이어서 보여준다.
  // 그러면 /me를 처음 한 번만 받아서, 그 뒤에 생긴 공지(하루 한 번 결제 오픈 공지 등)가 뜨지 않았다 (2026-10-06).
  // → 화면이 다시 보일 때(앱 전환·잠금 해제·뒤로 가기 복원) /me를 다시 받는다. 너무 자주는 안 받게 1분에 한 번까지.
  useEffect(() => {
    let last = Date.now();
    const again = () => {
      if (document.visibilityState !== "visible" || Date.now() - last < 60_000) return;
      last = Date.now();
      void refresh();
    };
    const onPageShow = (e: PageTransitionEvent) => {
      if (e.persisted) {
        last = 0;
        again();
      }
    };
    document.addEventListener("visibilitychange", again);
    window.addEventListener("focus", again);
    window.addEventListener("pageshow", onPageShow);
    return () => {
      document.removeEventListener("visibilitychange", again);
      window.removeEventListener("focus", again);
      window.removeEventListener("pageshow", onPageShow);
    };
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
