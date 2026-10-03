"use client";

import { useCallback, useState } from "react";
import { Button, Notice, PageTitle, Spinner } from "@/components/ui";
import { USER_STATUS_LABEL, adminApi } from "@/lib/admin";
import { errorMessage } from "@/lib/api";
import { cn, dateTime, parseTime } from "@/lib/format";
import { usePolling } from "@/lib/polling";

type PaymentRow = {
  payment_id: string;
  kind: "SIGNUP" | "VIP";
  code: string;
  amount: number;
  status: "REQUESTED" | "CONFIRMED" | "REJECTED" | "REFUNDED";
  user_status: string | null;
  requested_at: string | null;
  processed_at: string | null;
  processed_by: string | null;
  refundable: boolean;
};

const TABS = [
  { value: "pending", label: "확인 대기" },
  { value: "history", label: "지난 내역" },
] as const;

const STATUS_LABEL: Record<string, string> = {
  REQUESTED: "확인 대기",
  CONFIRMED: "입금 확인",
  REJECTED: "입금 없음",
  REFUNDED: "환불",
};

const PROMISE_MINUTES = 15; // 사용자에게 "15분 이내 확인"이라고 안내함

/** 가입비·VIP 입금 확인 (2026-10-03). 은행 앱의 입금자명(결제 코드)·금액과 맞춰 보고 처리한다.
 *  닉네임·이메일은 보여주지 않는다 (익명성). */
export default function PaymentsPage() {
  const [view, setView] = useState<(typeof TABS)[number]["value"]>("pending");
  const [rows, setRows] = useState<PaymentRow[] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());

  const load = useCallback(() => {
    setNow(Date.now());
    return adminApi<{ payments: PaymentRow[] }>(`/payments?view=${view}`)
      .then((r) => setRows(r.payments))
      .catch((err) => setError(errorMessage(err)));
  }, [view]);

  // 확인 대기 목록은 30초마다 새로 고침
  usePolling(load, 30_000, [view]);

  async function act(row: PaymentRow, action: "confirm" | "reject" | "refund") {
    if (action === "refund" && !window.confirm(`${row.code} (${row.amount.toLocaleString()}원)을 환불 처리할까요?\n사용자 계좌로 송금을 먼저 끝낸 뒤 누르세요.`)) return;
    setError("");
    setBusy(row.payment_id + action);
    try {
      await adminApi(`/payments/${row.payment_id}/${action}`, { method: "POST" });
      await load();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  const minutesWaiting = (iso: string | null) => (iso ? Math.floor((now - parseTime(iso).getTime()) / 60000) : 0);

  return (
    <>
      <PageTitle
        eyebrow="결제"
        title="입금 확인"
        desc="은행 앱에서 입금자명(결제 코드)과 금액이 맞는지 확인한 뒤 처리하세요. 가입비와 VIP가 함께 나와요. 사용자에게는 15분 이내 확인이라고 안내돼 있어요."
      />
      <div className="mb-6 flex gap-6 border-b border-line text-[14px]">
        {TABS.map((t) => (
          <button
            key={t.value}
            onClick={() => {
              setRows(null);
              setView(t.value);
            }}
            className={view === t.value ? "-mb-px border-b-2 border-ink pb-3 font-semibold" : "pb-3 text-ink-faint hover:text-ink"}
          >
            {t.label}
          </button>
        ))}
      </div>

      {error && (
        <div className="mb-4">
          <Notice tone="error">{error}</Notice>
        </div>
      )}

      {!rows ? (
        <Spinner />
      ) : rows.length === 0 ? (
        <p className="py-12 text-center text-[14px] text-ink-faint">{view === "pending" ? "확인할 입금이 없어요." : "비어 있어요."}</p>
      ) : (
        <ul className="divide-y divide-line rounded-card border border-line bg-paper-card">
          {rows.map((p) => {
            const waited = minutesWaiting(p.requested_at);
            const late = view === "pending" && waited >= PROMISE_MINUTES;
            return (
              <li key={p.payment_id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
                <div>
                  <span className="font-mono text-[16px] font-semibold tracking-wider">{p.code}</span>
                  <span className="num ml-3 text-[14px]">{p.amount.toLocaleString()}원</span>
                  <span className={cn("ml-2 rounded px-1.5 py-0.5 text-[11.5px]", p.kind === "VIP" ? "bg-brick-wash text-brick" : "bg-paper-deep text-ink-soft")}>
                    {p.kind === "VIP" ? "VIP" : "가입비"}
                  </span>
                  {p.user_status && p.user_status !== "ACTIVE" && (
                    <span className="ml-2 rounded bg-paper-deep px-1.5 py-0.5 text-[11.5px] text-ink-soft">
                      {USER_STATUS_LABEL[p.user_status] ?? p.user_status}
                    </span>
                  )}
                  <p className={cn("mt-1 text-[12.5px]", late ? "font-semibold text-brick" : "text-ink-faint")}>
                    {view === "pending" ? (
                      <>
                        {p.requested_at && dateTime(p.requested_at)} 요청 · {waited}분 지남{late && " (15분 넘음)"}
                      </>
                    ) : (
                      <>
                        {STATUS_LABEL[p.status]} · {p.processed_at && dateTime(p.processed_at)}
                        {p.processed_by && ` · ${p.processed_by}`}
                      </>
                    )}
                  </p>
                </div>
                <div className="flex gap-2">
                  {view === "pending" && (
                    <>
                      <Button size="sm" loading={busy === p.payment_id + "confirm"} onClick={() => act(p, "confirm")}>
                        입금 확인
                      </Button>
                      <Button size="sm" variant="secondary" loading={busy === p.payment_id + "reject"} onClick={() => act(p, "reject")}>
                        입금 없음
                      </Button>
                    </>
                  )}
                  {view === "history" && p.status === "REJECTED" && (
                    <Button size="sm" variant="secondary" loading={busy === p.payment_id + "confirm"} onClick={() => act(p, "confirm")}>
                      입금 확인으로 바꾸기
                    </Button>
                  )}
                  {view === "history" && p.status === "CONFIRMED" && p.kind === "SIGNUP" && (
                    <Button
                      size="sm"
                      variant="danger"
                      disabled={!p.refundable}
                      title={p.refundable ? undefined : "사진 검수를 받은 사용자는 환불할 수 없어요"}
                      loading={busy === p.payment_id + "refund"}
                      onClick={() => act(p, "refund")}
                    >
                      환불 처리
                    </Button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
      {view === "history" && (
        <p className="mt-4 text-[12.5px] text-ink-faint">
          가입비 환불: 사용자가 고객센터 메일로 보낸 계좌로 먼저 송금한 뒤 [환불 처리]를 누르세요. 사진 검수를 받은 사용자(반려 포함)는 환불할 수 없어요. VIP는 입금 확인 후 환불하지 않아요.
        </p>
      )}
    </>
  );
}
