"use client";

import { useCallback, useEffect, useState } from "react";
import { Button, Notice, PageTitle, Spinner } from "@/components/ui";
import { adminApi } from "@/lib/admin";
import { errorMessage } from "@/lib/api";
import { cn, dateTime } from "@/lib/format";

type Response = {
  id: string;
  gender: "MALE" | "FEMALE" | null;
  improvement: string | null;
  feature_request: string | null;
  created_at: string;
};
type Data = {
  open: boolean;
  total: number;
  by_gender: { MALE: number; FEMALE: number };
  written: number;
  skipped: number;
  responses: Response[];
};

const GENDER_LABEL: Record<string, string> = { MALE: "남", FEMALE: "여" };

/**
 * 설문 (2026-10-05, 2026-11-14 개선점·바라는 기능 설문으로 바꿈)
 * - "설문 시작하기"를 켜면 아직 답하지 않은 사용자에게 로그인·가입 직후 설문이 먼저 뜬다 (건너뛰기 가능)
 * - 끄면 바로 아무에게도 안 뜬다. 응답은 그대로 남는다
 * - 닉네임·이메일 없이 성별만 보여준다
 */
export default function SurveyAdminPage() {
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState<"all" | "improvement" | "feature">("all");

  const load = useCallback(
    () =>
      adminApi<Data>("/survey")
        .then((r) => {
          setData(r);
          setError("");
        })
        .catch((e) => setError(errorMessage(e))),
    [],
  );

  useEffect(() => {
    load();
  }, [load]);

  async function toggle() {
    if (!data) return;
    const next = !data.open;
    const msg = next
      ? "설문을 시작할까요?\n\n아직 답하지 않은 모든 사용자에게 다음 접속 때 설문이 먼저 떠요. (쓸 말이 없으면 건너뛸 수 있어요)"
      : "설문을 끝낼까요?\n\n바로 아무에게도 뜨지 않아요. 지금까지의 응답은 그대로 남아요.";
    if (!window.confirm(msg)) return;
    setBusy(true);
    try {
      await adminApi("/survey/open", { method: "PUT", body: { open: next } });
      await load();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  if (!data) return error ? <Notice tone="error">{error}</Notice> : <Spinner />;

  const shown = data.responses.filter((r) =>
    tab === "improvement" ? r.improvement : tab === "feature" ? r.feature_request : true,
  );
  const tabs: { key: typeof tab; label: string; count: number }[] = [
    { key: "all", label: "전체", count: data.responses.length },
    { key: "improvement", label: "개선할 점", count: data.responses.filter((r) => r.improvement).length },
    { key: "feature", label: "바라는 기능", count: data.responses.filter((r) => r.feature_request).length },
  ];

  return (
    <div className="space-y-10">
      <PageTitle title="설문" desc="1) 개선했으면 하는 점 · 2) 새로 생겼으면 하는 기능. 계정당 한 번만 답하고, 쓸 말이 없으면 건너뛸 수 있어요." />

      <section className="flex flex-wrap items-center justify-between gap-4 rounded-card border border-line bg-paper-card px-5 py-4">
        <div>
          <p className="text-[15px] font-semibold text-ink">
            {data.open ? "설문 받는 중" : "설문 꺼짐"}
            <span className={cn("ml-2 inline-block h-2 w-2 rounded-full align-middle", data.open ? "bg-moss" : "bg-line-strong")} />
          </p>
          <p className="mt-1 text-[13px] text-ink-soft">
            응답 <b className="num text-ink">{data.total}</b>명 (남 {data.by_gender.MALE} · 여 {data.by_gender.FEMALE}) · 의견 적음{" "}
            <b className="num text-ink">{data.written}</b> · 건너뜀 <b className="num text-ink">{data.skipped}</b>
          </p>
        </div>
        <Button variant={data.open ? "danger" : "primary"} onClick={toggle} loading={busy}>
          {data.open ? "설문 끝내기" : "설문 시작하기"}
        </Button>
      </section>

      {error && <Notice tone="error">{error}</Notice>}

      <section>
        <div className="mb-3 flex flex-wrap gap-2">
          {tabs.map((t) => (
            <button
              key={t.key}
              type="button"
              onClick={() => setTab(t.key)}
              className={cn(
                "rounded-full border px-3 py-1 text-[13px]",
                tab === t.key ? "border-ink bg-ink text-paper" : "border-line text-ink-soft hover:border-line-strong",
              )}
            >
              {t.label} <span className="num">{t.count}</span>
            </button>
          ))}
        </div>
        {shown.length === 0 ? (
          <p className="text-[14px] text-ink-faint">아직 적은 의견이 없어요.</p>
        ) : (
          <ul className="divide-y divide-line rounded-card border border-line bg-paper-card">
            {shown.map((r) => (
              <li key={r.id} className="space-y-1.5 px-5 py-4 text-[14px]">
                <p className="text-[12.5px] text-ink-faint">
                  {r.gender ? GENDER_LABEL[r.gender] : "성별 없음"} · {dateTime(r.created_at)}
                </p>
                {r.improvement && tab !== "feature" && <Line label="개선할 점">{r.improvement}</Line>}
                {r.feature_request && tab !== "improvement" && <Line label="바라는 기능">{r.feature_request}</Line>}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function Line({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <p className="whitespace-pre-wrap leading-relaxed text-ink">
      <span className="mr-2 text-[12.5px] text-ink-faint">{label}</span>
      {children}
    </p>
  );
}
