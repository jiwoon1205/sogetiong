"use client";

import { SalePrice } from "@/components/DiscountTag";
import { useCallback, useRef, useState } from "react";
import { Button, Notice, Spinner } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { openTime } from "@/lib/format";
import { usePolling } from "@/lib/polling";
import { hasPayment, type PaymentDetail, type PaymentInfo } from "@/lib/types";

/** 첫 이용권 입금 단계 (2026-10-03 가입비, 2026-10-04 구독제). 운영자 통장으로 직접 입금 → 관리자가 확인하면 사진 제출이 열린다.
 *  이용권 기간(정식 2주, 베타 기간 구매 4주)은 사진 검수가 끝나 추천이 열리는 날부터 센다.
 *
 *  - 입금자명에는 실명 대신 결제 코드를 적게 한다 (익명성).
 *  - 오전 6시 ~ 밤 12시만 결제할 수 있다. 밤에는 계좌번호를 숨긴다.
 *  - "입금했어요"를 누른 뒤에는 30초마다 확인해서, 확인되면 onConfirmed로 다음 단계로 넘어간다.
 */
export function PaymentStep({ onConfirmed }: { onConfirmed: () => void }) {
  const [info, setInfo] = useState<PaymentDetail | null>(null);
  const [error, setError] = useState("");
  const [sending, setSending] = useState(false);

  const load = useCallback(async () => {
    try {
      const next = await api<PaymentInfo>("/me/payment");
      if (!next.required || !hasPayment(next)) {
        onConfirmed();
        return;
      }
      setInfo(next);
    } catch (err) {
      setError(errorMessage(err));
    }
  }, [onConfirmed]);

  // 처음 한 번 + (확인 대기 중이거나 운영 시간 외이면) 30초마다 다시 확인
  const shouldPoll = info === null || info.status === "REQUESTED" || !info.open_now;
  usePolling(
    () => {
      if (shouldPoll) void load();
    },
    30_000,
    [shouldPoll],
  );

  async function request() {
    setError("");
    setSending(true);
    try {
      const next = await api<PaymentInfo>("/me/payment/request", { method: "POST" });
      if (hasPayment(next)) setInfo(next);
    } catch (err) {
      setError(errorMessage(err));
      void load(); // 운영 시간이 막 끝난 경우 화면을 새로 그린다
    } finally {
      setSending(false);
    }
  }

  if (!info) return error ? <Notice tone="error">{error}</Notice> : <Spinner />;

  return (
    <PaymentPanel
      info={info}
      sending={sending}
      error={error}
      onRequest={request}
      waitingText={
        "입금 후 15분 이내 확인돼요. 확인되면 자동으로 사진 제출 화면으로 넘어가요." + maintenanceNote(info.membership?.before_open ? info.membership.open_at : null)
      }
      refundNote={REFUND_NOTE}
    />
  );
}

/** 유료 시작 전에 결제하면 이용권 기간이 유료 시작 시각부터 시작된다는 안내 (2026-10-04, 2026-10-06 점검 기간 없앰) */
function maintenanceNote(openAt: string | null | undefined): string {
  return openAt ? ` 이용권 기간은 사진 평가가 끝난 뒤, 빨라도 유료 시작(${openTime(openAt)})부터 시작돼요.` : "";
}

export const REFUND_NOTE =
  "환불은 첫 이용권을 사진 검수 전에 취소할 때만 돼요. 사진이 반려돼도 검수를 받은 것이라 환불되지 않고, 연장 결제는 입금 확인 후 환불되지 않아요.";

/** 기본 이용권 연장·다시 사기 (2026-10-04 구독제). 이용권이 끝났을 때 화면, 설정 화면에서 쓴다.
 *  언제든 살 수 있고, 남아 있으면 끝나는 날 뒤에 기간(m.days)이 붙는다. 확인되면 onActivated를 부른다. */
/** 다른 화면에서 "결제창을 바로 펼쳐서" 설정으로 보낼 때 쓰는 표시 (sessionStorage, 2026-10-08) */
export const OPEN_PAY_KEY = "open-membership-pay";

export function MembershipRenew({ onActivated, autoOpen = false }: { onActivated: () => void; autoOpen?: boolean }) {
  const [info, setInfo] = useState<PaymentDetail | null>(null);
  const [error, setError] = useState("");
  const [sending, setSending] = useState(false);
  // autoOpen (2026-10-08): "이용권 사러 가기"로 들어오면 결제창(계좌·입금자명)을 바로 펼친다
  const [paying, setPaying] = useState(autoOpen);
  const last = useRef<PaymentDetail | null>(null);

  const load = useCallback(async () => {
    try {
      const next = await api<PaymentInfo>("/me/payment");
      if (!hasPayment(next)) return;
      // 확인 대기 중이던 결제가 처리돼서 새 코드가 나왔다 = 이용권이 늘어남
      const prev = last.current;
      last.current = next;
      if (prev?.status === "REQUESTED" && next.code !== prev.code) {
        setPaying(false);
        onActivated();
      } else if (next.status !== "CREATED") setPaying(true);
      setInfo(next);
    } catch (err) {
      setError(errorMessage(err));
    }
  }, [onActivated]);

  const shouldPoll = info === null || info.status === "REQUESTED";
  usePolling(
    () => {
      if (shouldPoll) void load();
    },
    30_000,
    [shouldPoll],
  );

  async function request() {
    setError("");
    setSending(true);
    try {
      const next = await api<PaymentInfo>("/me/payment/request", { method: "POST" });
      if (hasPayment(next)) {
        last.current = next;
        setInfo(next);
      }
    } catch (err) {
      setError(errorMessage(err));
      void load();
    } finally {
      setSending(false);
    }
  }

  if (!info) return error ? <Notice tone="error">{error}</Notice> : <Spinner />;
  const m = info.membership;
  const days = m?.days ?? 14;
  if (!paying)
    return (
      <Button size="lg" className="w-full" onClick={() => setPaying(true)}>
        <span>
          {m?.status === "active" ? "미리 연장하기" : "기본 이용권 시작하기"} · {days}일{" "}
          <SalePrice m={m} price={info.amount} strikeClass="font-normal opacity-60" />
        </span>
      </Button>
    );
  return (
    <PaymentPanel
      info={info}
      sending={sending}
      error={error}
      onRequest={request}
      waitingText={
        m?.before_open && m.open_at
          ? `입금 후 15분 이내 확인돼요. 지금은 무료 베타 기간이라 ${days}일은 유료 시작(${openTime(m.open_at)})부터 시작돼요.`
          : m?.status === "active"
            ? `입금 후 15분 이내 확인돼요. 지금 남은 기간 뒤에 ${days}일이 더해져요.`
            : `입금 후 15분 이내 확인돼요. 확인되면 ${days}일 뒤 밤 12시까지 이용할 수 있어요.`
      }
      refundNote={REFUND_NOTE}
    />
  );
}

/** 결제 방법 3단계 (2026-10-07): 입금자명을 안 바꾸거나 "입금 완료" 버튼을 안 누르는 사람이 많아 강조 */
function PayHowTo({ amount, code }: { amount: number; code: string }) {
  const step = "flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brick text-[13px] font-semibold text-paper";
  return (
    <div className="rounded-card border-2 border-brick bg-brick-wash px-4 py-4">
      <p className="text-[14.5px] font-semibold text-brick-deep">결제 방법 · 3단계를 모두 해야 끝나요</p>
      <ol className="mt-3 space-y-3 text-[14px] leading-relaxed text-ink">
        <li className="flex gap-2.5">
          <span className={step}>1</span>
          <span>
            위 계좌로 <b>{amount.toLocaleString()}원</b>을 보내요.
          </span>
        </li>
        <li className="flex gap-2.5">
          <span className={step}>2</span>
          <span>
            보낼 때 <b>입금자명(받는 분에게 표시)</b>을 실명이 아니라 <b className="num text-[16px] tracking-wider text-brick">{code}</b>로 꼭 바꿔요.
            <span className="mt-0.5 block text-[12.5px] text-ink-soft">바꾸지 않으면 누가 보낸 돈인지 알 수 없어서 확인이 안 돼요.</span>
          </span>
        </li>
        <li className="flex gap-2.5">
          <span className={step}>3</span>
          <span>
            이 화면으로 돌아와 아래 <b>&lsquo;입금 완료했어요&rsquo;</b> 버튼을 꼭 눌러요.
            <span className="mt-0.5 block text-[12.5px] text-ink-soft">버튼을 눌러야 운영자에게 확인 요청이 가요. 안 누르면 입금해도 이용권이 시작되지 않아요.</span>
          </span>
        </li>
      </ol>
    </div>
  );
}

/** 입금 안내 화면 (이용권·VIP 공통): 계좌·결제 코드, "입금 완료했어요" 버튼, 안내 문구 */
export function PaymentPanel({
  info,
  sending,
  error,
  onRequest,
  waitingText,
  refundNote,
}: {
  info: PaymentDetail;
  sending: boolean;
  error: string;
  onRequest: () => void;
  waitingText: string;
  refundNote: string;
}) {
  const hours = `오전 ${info.open_hour}시 ~ ${info.close_hour === 24 ? "밤 12시" : `${info.close_hour}시`}`;
  const waiting = info.status === "REQUESTED";

  return (
    <div className="space-y-6">
      {!info.open_now && !waiting ? (
        <Notice>
          <p className="font-semibold text-ink">운영 시간 외입니다</p>
          <p className="mt-1">오전 {info.open_hour}시부터 결제할 수 있어요. ({hours})</p>
        </Notice>
      ) : (
        <>
          <dl className="divide-y divide-line rounded-md border border-line">
            <Row label="금액" value={`${info.amount.toLocaleString()}원`} />
            <Row label="은행" value={info.bank_name ?? ""} />
            <Row label="계좌번호" value={info.account_number ?? ""} copy />
            <Row label="예금주" value={info.account_holder ?? ""} />
            <Row label="입금자명" value={info.code} copy strong />
          </dl>
          {!waiting && <PayHowTo amount={info.amount} code={info.code} />}
        </>
      )}

      {waiting ? (
        <Notice tone="ok">
          <p className="font-semibold">입금을 확인하고 있어요</p>
          <p className="mt-1">{waitingText}</p>
        </Notice>
      ) : (
        info.open_now && (
          <>
            {info.status === "REJECTED" && (
              <Notice tone="error">
                입금이 확인되지 않았어요. 금액({info.amount.toLocaleString()}원)과 입금자명({info.code})을 확인한 뒤 다시 눌러 주세요.
              </Notice>
            )}
            <p className="text-center text-[13.5px] font-semibold text-brick">
              ⚠️ 입금한 뒤 아래 버튼을 꼭 눌러 주세요. 누르지 않으면 확인이 시작되지 않아요.
            </p>
            <Button size="lg" className="-mt-3 w-full" loading={sending} onClick={onRequest}>
              입금 완료했어요
            </Button>
          </>
        )
      )}

      {error && <Notice tone="error">{error}</Notice>}

      <ul className="list-disc space-y-1.5 pl-5 text-[13px] leading-relaxed text-ink-soft">
        <li>&lsquo;입금 완료했어요&rsquo;를 누른 뒤 15분 이내 확인돼요.</li>
        <li>입금자명을 바꾸지 못하고 보냈다면 보낸 이름·시각·금액을 문의 메일로 알려 주세요.</li>
        <li>
          결제는 {hours}에 할 수 있어요. 그 밖의 시간에 보낸 입금은 오전 {info.open_hour}시 이후 확인돼요.
        </li>
        <li>{refundNote}</li>
        <li>
          문의:{" "}
          <a href={`mailto:${info.support_email}`} className="underline underline-offset-4">
            {info.support_email}
          </a>
        </li>
      </ul>
    </div>
  );
}

function Row({ label, value, copy, strong }: { label: string; value: string; copy?: boolean; strong?: boolean }) {
  const [copied, setCopied] = useState(false);
  async function doCopy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* 복사를 못 하는 브라우저 → 직접 보고 적으면 된다 */
    }
  }
  return (
    <div className="flex items-center justify-between gap-3 px-4 py-3">
      <dt className="text-[13px] text-ink-faint">{label}</dt>
      <dd className="flex items-center gap-2">
        <span className={strong ? "num text-[17px] font-semibold tracking-wider text-ink" : "num text-[15px] text-ink"}>{value}</span>
        {copy && (
          <button type="button" onClick={doCopy} className="text-[12px] text-ink-soft underline underline-offset-4 hover:text-ink">
            {copied ? "복사됨" : "복사"}
          </button>
        )}
      </dd>
    </div>
  );
}
