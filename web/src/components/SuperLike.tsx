"use client";

import { useCallback, useRef, useState } from "react";
import { PaymentPanel } from "@/components/PaymentStep";
import { Button, Modal, Notice, Spinner } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { usePolling } from "@/lib/polling";
import type { SuperLikeInfo } from "@/lib/types";

/** 슈퍼 라이크 (2026-10-12).
 *  - 추천 화면 가운데 작은 동그라미 버튼. 보내면 상대가 LIKE하지 않아도 바로 매칭된다.
 *  - 보낸 사람은 상대가 답장하기 전까지 메시지 1개만 보낼 수 있다 (서버가 막음).
 *  - 1개 1,000원, 직접 입금으로 1~10개를 산다. 기간 없음.
 */

export function StarIcon({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden>
      <path
        d="M12 2.8l2.8 5.9 6.4.8-4.7 4.4 1.2 6.4L12 17.2l-5.7 3.1 1.2-6.4-4.7-4.4 6.4-.8z"
        fill="currentColor"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinejoin="round"
      />
    </svg>
  );
}

const SUPER_REFUND_NOTE = "산 슈퍼 라이크는 기간 없이 쌓여요. 하나도 쓰지 않았을 때만 환불돼요. 쓴 슈퍼 라이크는 환불되지 않아요.";

/** 슈퍼 라이크 사기: 개수 고르기 → 계좌·결제 코드 → "입금 완료했어요" → 관리자가 확인하면 onBought */
export function SuperLikeBuy({ onBought }: { onBought: (count: number) => void }) {
  const [info, setInfo] = useState<SuperLikeInfo | null>(null);
  const [error, setError] = useState("");
  const [sending, setSending] = useState(false);
  const [changing, setChanging] = useState(false);
  const startCount = useRef<number | null>(null);

  const load = useCallback(
    async (quantity?: number) => {
      try {
        const next = await api<SuperLikeInfo>(`/me/super-likes${quantity ? `?quantity=${quantity}` : ""}`);
        if (startCount.current === null) startCount.current = next.count;
        else if (next.count > startCount.current) {
          onBought(next.count); // 관리자가 입금을 확인해서 개수가 늘었다
          return;
        }
        setInfo(next);
      } catch (err) {
        setError(errorMessage(err));
      }
    },
    [onBought],
  );

  const waiting = info?.payment?.status === "REQUESTED";
  usePolling(
    () => {
      if (info === null || waiting) void load();
    },
    30_000,
    [waiting, info === null],
  );

  async function setQuantity(q: number) {
    setChanging(true);
    await load(q);
    setChanging(false);
  }

  async function request() {
    if (!info?.payment) return;
    setSending(true);
    setError("");
    try {
      const next = await api<SuperLikeInfo>(`/me/super-likes/request?quantity=${info.payment.quantity}`, { method: "POST" });
      setInfo(next);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSending(false);
    }
  }

  if (!info) return error ? <Notice tone="error">{error}</Notice> : <Spinner />;
  if (!info.can_buy || !info.payment) return <Notice>{info.blocked_reason ?? "지금은 살 수 없어요."}</Notice>;
  const p = info.payment;
  const editable = p.status === "CREATED";

  return (
    <div className="space-y-5">
      <div className="rounded-card border border-line bg-paper-card px-4 py-4">
        <p className="text-[13px] text-ink-faint">개수 고르기 · 1개 {info.price.toLocaleString()}원</p>
        <div className="mt-2 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <button
              type="button"
              aria-label="하나 빼기"
              disabled={!editable || changing || p.quantity <= 1}
              onClick={() => setQuantity(p.quantity - 1)}
              className="flex h-9 w-9 items-center justify-center rounded-full border border-line-strong text-[18px] disabled:opacity-35"
            >
              −
            </button>
            <span className="num w-8 text-center text-[22px] font-semibold">{p.quantity}</span>
            <button
              type="button"
              aria-label="하나 더하기"
              disabled={!editable || changing || p.quantity >= info.max_quantity}
              onClick={() => setQuantity(p.quantity + 1)}
              className="flex h-9 w-9 items-center justify-center rounded-full border border-line-strong text-[18px] disabled:opacity-35"
            >
              +
            </button>
          </div>
          <p className="num text-[20px] font-semibold text-brick">{p.amount.toLocaleString()}원</p>
        </div>
        {!editable && <p className="mt-2 text-[12.5px] text-ink-faint">입금 확인을 요청한 뒤에는 개수를 바꿀 수 없어요.</p>}
      </div>
      <PaymentPanel
        info={p}
        sending={sending}
        error={error}
        onRequest={request}
        waitingText={`입금 후 15분 이내 확인돼요. 확인되면 슈퍼 라이크 ${p.quantity}개가 들어와요.`}
        refundNote={SUPER_REFUND_NOTE}
      />
    </div>
  );
}

/** 추천 화면에서 슈퍼 라이크 버튼을 누르면 여는 창. 남은 게 있으면 "보낼까요?", 없으면 사기 */
export function SuperLikeSheet({
  open,
  nickname,
  count,
  sending,
  error,
  onSend,
  onClose,
  onBought,
}: {
  open: boolean;
  nickname: string;
  count: number;
  sending: boolean;
  error: string;
  onSend: () => void;
  onClose: () => void;
  onBought: (count: number) => void;
}) {
  const [buying, setBuying] = useState(false);
  const showBuy = buying || count <= 0;
  return (
    <Modal open={open} onClose={onClose} title={showBuy ? "슈퍼 라이크 사기" : "슈퍼 라이크 보내기"}>
      {showBuy ? (
        <>
          <p className="mb-4 text-[14px] leading-relaxed text-ink-soft">
            슈퍼 라이크를 보내면 상대가 좋아요를 누르지 않아도 <b className="font-semibold text-ink">바로 대화가 열려요.</b>
          </p>
          <SuperLikeBuy
            onBought={(n) => {
              setBuying(false);
              onBought(n);
            }}
          />
        </>
      ) : (
        <>
          <div className="rounded-card border border-brick/30 bg-brick-wash px-4 py-4 text-center">
            <span className="mx-auto flex h-11 w-11 items-center justify-center rounded-full bg-brick text-paper">
              <StarIcon className="h-5 w-5" />
            </span>
            <p className="mt-3 text-[15px] leading-relaxed text-ink">
              <b className="font-semibold">{nickname}</b>님에게 슈퍼 라이크를 보낼까요?
            </p>
            <p className="mt-1 text-[13px] text-ink-soft">
              남은 슈퍼 라이크 <b className="num font-semibold text-brick">{count}</b>개 · 1개를 써요
            </p>
          </div>
          <ul className="mt-4 space-y-1.5 text-[13.5px] leading-relaxed text-ink-soft">
            <li>⭐ 상대가 좋아요를 누르지 않아도 바로 매칭돼요. 상대에게는 &lsquo;슈퍼 라이크로 연결됐어요&rsquo;라고 보여요.</li>
            <li>💬 상대가 답장하기 전까지 메시지는 1개만 보낼 수 있어요. 첫 메시지를 신중하게 써 주세요.</li>
            <li>↩️ 보낸 슈퍼 라이크는 되돌리거나 환불할 수 없어요.</li>
          </ul>
          {error && (
            <div className="mt-4">
              <Notice tone="error">{error}</Notice>
            </div>
          )}
          <div className="mt-5 space-y-2.5">
            <Button size="lg" className="w-full" loading={sending} onClick={onSend}>
              슈퍼 라이크 보내기
            </Button>
            <Button variant="ghost" className="w-full" onClick={() => setBuying(true)}>
              슈퍼 라이크 더 사기
            </Button>
          </div>
        </>
      )}
    </Modal>
  );
}
