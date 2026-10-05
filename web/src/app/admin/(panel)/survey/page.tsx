"use client";

import { useCallback, useEffect, useState } from "react";
import { Button, Notice, PageTitle, Spinner } from "@/components/ui";
import { adminApi } from "@/lib/admin";
import { errorMessage } from "@/lib/api";
import { cn, dateTime } from "@/lib/format";

type Bucket = { label: string; total: number; MALE: number; FEMALE: number };
type Response = {
  id: string;
  gender: "MALE" | "FEMALE" | null;
  appearance_choice: string;
  appearance_comment: string | null;
  payment_rating: number;
  payment_comment: string | null;
  suggestion: string | null;
  created_at: string;
};
type Data = {
  open: boolean;
  total: number;
  by_gender: { MALE: number; FEMALE: number };
  appearance: (Bucket & { key: string })[];
  payment: (Bucket & { score: number })[];
  payment_average: number | null;
  responses: Response[];
};

const GENDER_LABEL: Record<string, string> = { MALE: "남", FEMALE: "여" };

/**
 * 설문 (2026-10-05)
 * - "설문 받기"를 켜면 아직 답하지 않은 사용자는 로그인·가입 직후 설문을 꼭 답해야 넘어간다
 * - 끄면 바로 아무에게도 안 뜬다. 응답은 그대로 남는다
 * - 닉네임·이메일 없이 성별만 보여준다
 */
export default function SurveyAdminPage() {
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

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
      ? "설문을 시작할까요?\n\n아직 답하지 않은 모든 사용자가 다음 접속 때 설문을 꼭 답해야 서비스를 쓸 수 있어요."
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

  const labelOf = (key: string) => data.appearance.find((a) => a.key === key)?.label ?? key;
  const ratingLabel = (s: number) => data.payment.find((p) => p.score === s)?.label ?? String(s);
  const withText = data.responses.filter((r) => r.appearance_comment || r.payment_comment || r.suggestion);

  return (
    <div className="space-y-10">
      <PageTitle title="설문" desc="정식 오픈 전 설문: 외모 평가 방식 · 유료 방식 만족도 · 기타 의견. 계정당 한 번만 답할 수 있어요." />

      <section className="flex flex-wrap items-center justify-between gap-4 rounded-card border border-line bg-paper-card px-5 py-4">
        <div>
          <p className="text-[15px] font-semibold text-ink">
            {data.open ? "설문 받는 중" : "설문 꺼짐"}
            <span className={cn("ml-2 inline-block h-2 w-2 rounded-full align-middle", data.open ? "bg-moss" : "bg-line-strong")} />
          </p>
          <p className="mt-1 text-[13px] text-ink-soft">
            응답 <b className="num text-ink">{data.total}</b>명 (남 {data.by_gender.MALE} · 여 {data.by_gender.FEMALE})
          </p>
        </div>
        <Button variant={data.open ? "danger" : "primary"} onClick={toggle} loading={busy}>
          {data.open ? "설문 끝내기" : "설문 시작하기"}
        </Button>
      </section>

      {error && <Notice tone="error">{error}</Notice>}

      <section>
        <h2 className="mb-3 text-[15px] font-semibold">1. 외모 평가 방식</h2>
        <Bars rows={data.appearance} total={data.total} />
      </section>

      <section>
        <h2 className="mb-3 text-[15px] font-semibold">
          2. 유료 방식 만족도
          {data.payment_average !== null && (
            <span className="ml-2 text-[13px] font-normal text-ink-soft">
              평균 <b className="num text-ink">{data.payment_average}</b> / 5
            </span>
          )}
        </h2>
        <Bars rows={data.payment} total={data.total} />
      </section>

      <section>
        <h2 className="mb-3 text-[15px] font-semibold">적은 의견 ({withText.length})</h2>
        {withText.length === 0 ? (
          <p className="text-[14px] text-ink-faint">아직 적은 의견이 없어요.</p>
        ) : (
          <ul className="divide-y divide-line rounded-card border border-line bg-paper-card">
            {withText.map((r) => (
              <li key={r.id} className="space-y-1.5 px-5 py-4 text-[14px]">
                <p className="text-[12.5px] text-ink-faint">
                  {r.gender ? GENDER_LABEL[r.gender] : "성별 없음"} · {dateTime(r.created_at)} · {labelOf(r.appearance_choice)} · 유료 {ratingLabel(r.payment_rating)}
                </p>
                {r.appearance_comment && <Line label="외모 평가">{r.appearance_comment}</Line>}
                {r.payment_comment && <Line label="유료 방식">{r.payment_comment}</Line>}
                {r.suggestion && <Line label="기타">{r.suggestion}</Line>}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function Bars({ rows, total }: { rows: Bucket[]; total: number }) {
  return (
    <div className="space-y-2.5 rounded-card border border-line bg-paper-card px-5 py-4">
      {rows.map((r) => {
        const pct = total ? Math.round((r.total / total) * 100) : 0;
        return (
          <div key={r.label} className="grid grid-cols-[minmax(0,12rem)_1fr_auto] items-center gap-3 text-[13.5px]">
            <span className="truncate text-ink-soft" title={r.label}>
              {r.label}
            </span>
            <span className="relative h-[6px] rounded-full bg-line">
              <span className="absolute inset-y-0 left-0 rounded-full bg-ink" style={{ width: `${pct}%` }} />
            </span>
            <span className="num whitespace-nowrap text-right text-ink">
              <b>{r.total}</b>명 · {pct}%<span className="ml-2 text-[12px] text-ink-faint">남 {r.MALE} · 여 {r.FEMALE}</span>
            </span>
          </div>
        );
      })}
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
