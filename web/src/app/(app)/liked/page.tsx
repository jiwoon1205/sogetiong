"use client";

import { useCallback, useState } from "react";
import { MatchCelebration } from "@/components/MatchCelebration";
import { PaymentPanel } from "@/components/PaymentStep";
import { ProfileCard } from "@/components/ProfileCard";
import { Button, Notice, PageTitle, Spinner } from "@/components/ui";
import { ApiError, api, errorMessage } from "@/lib/api";
import { timeAgo, untilDay } from "@/lib/format";
import { usePolling } from "@/lib/polling";
import { markMatchSeen } from "@/lib/seenMatches";
import { useSession } from "@/lib/session";
import type { LikedMeCard, VipInfo } from "@/lib/types";

/** 받은 LIKE (2026-10-03).
 *  - VIP: 나를 LIKE한 사람 목록 (최근 순). 누르면 추천 카드와 같은 프로필 → LIKE(바로 매칭)·PASS
 *  - 일반: VIP 가격·기간·혜택 5가지 + 결제(직접 입금). "몇 명이 LIKE했는지"는 보여주지 않는다.
 */
export default function LikedPage() {
  const { refresh } = useSession();
  const [vip, setVip] = useState<VipInfo | null>(null);
  const [error, setError] = useState("");

  const loadVip = useCallback(async () => {
    try {
      setVip(await api<VipInfo>("/me/vip"));
    } catch (err) {
      setError(errorMessage(err));
    }
  }, []);

  // 처음 한 번 + 1분마다 (VIP가 끝나거나 시작되면 화면이 바뀐다)
  usePolling(loadVip, 60_000);

  if (!vip) return error ? <Notice tone="error">{error}</Notice> : <Spinner />;
  if (vip.active) return <LikedList vip={vip} />;
  return (
    <VipShop
      vip={vip}
      onChange={setVip}
      onActivated={() => {
        void refresh();
        void loadVip();
      }}
    />
  );
}

// ---------- VIP: 나를 LIKE한 사람 ----------

function LikedList({ vip }: { vip: VipInfo }) {
  const [rows, setRows] = useState<LikedMeCard[] | null>(null);
  const [open, setOpen] = useState<LikedMeCard | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [matched, setMatched] = useState<{ name: string; matchId: string } | null>(null);

  const load = useCallback(async () => {
    try {
      setRows((await api<{ profiles: LikedMeCard[] }>("/liked-me")).profiles);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) location.reload(); // 방금 VIP가 끝남
      else setError(errorMessage(err));
    }
  }, []);

  // 처음 한 번 + 1분마다 새로 LIKE한 사람 반영
  usePolling(load, 60_000);

  async function act(card: LikedMeCard, action: "like" | "pass") {
    setBusy(true);
    setError("");
    try {
      if (action === "like") {
        const res = await api<{ matched: boolean; match_id: string | null }>("/likes", { method: "POST", body: { profile_id: card.profile_id } });
        if (res.matched && res.match_id) {
          markMatchSeen(res.match_id);
          setMatched({ name: card.nickname, matchId: res.match_id });
        }
      } else {
        await api("/passes", { method: "POST", body: { profile_id: card.profile_id } });
      }
      setOpen(null);
      await load();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-app">
      <PageTitle
        eyebrow="VIP"
        title="받은 LIKE"
        desc={vip.until ? `VIP는 ${untilDay(vip.until)}예요.` : "나를 LIKE한 사람이에요. 서로 LIKE하면 바로 매칭돼요."}
      />
      {error && (
        <div className="mb-4">
          <Notice tone="error">{error}</Notice>
        </div>
      )}

      {open ? (
        <div>
          <button onClick={() => setOpen(null)} className="mb-4 text-[13.5px] text-ink-soft hover:text-ink">
            ← 목록으로
          </button>
          <ProfileCard card={open} />
          <div className="mt-6 grid grid-cols-2 gap-3">
            <Button variant="secondary" size="lg" disabled={busy} onClick={() => act(open, "pass")}>
              넘기기
            </Button>
            <Button size="lg" loading={busy} onClick={() => act(open, "like")}>
              좋아요 · 바로 매칭
            </Button>
          </div>
          <p className="mt-3 text-center text-[12.5px] text-ink-faint">여기서 누른 좋아요도 하루 좋아요 개수에 포함돼요.</p>
        </div>
      ) : !rows ? (
        <Spinner />
      ) : rows.length === 0 ? (
        <p className="py-16 text-center text-[14px] text-ink-faint">아직 나를 LIKE한 사람이 없어요.</p>
      ) : (
        <ul className="divide-y divide-line rounded-card border border-line bg-paper-card">
          {rows.map((r) => (
            <li key={r.profile_id}>
              <button onClick={() => setOpen(r)} className="flex w-full items-center justify-between gap-3 px-5 py-4 text-left hover:bg-paper-deep/60">
                <span className="min-w-0">
                  <span className="font-semibold">{r.nickname}</span>
                  <span className="ml-2 text-[13px] text-ink-soft">{[r.age ? `만 ${r.age}세` : null, r.campus].filter(Boolean).join(" · ")}</span>
                  {r.passed && <span className="ml-2 rounded bg-paper-deep px-1.5 py-0.5 text-[11.5px] text-ink-soft">넘김</span>}
                </span>
                <span className="shrink-0 text-[12.5px] text-ink-faint">{timeAgo(r.liked_at)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {matched && (
        <MatchCelebration
          partnerName={matched.name}
          matchId={matched.matchId}
          onClose={() => {
            markMatchSeen(matched.matchId);
            setMatched(null);
          }}
        />
      )}
    </div>
  );
}

// ---------- 일반: VIP 안내·결제 ----------

function VipShop({ vip, onChange, onActivated }: { vip: VipInfo; onChange: (v: VipInfo) => void; onActivated: () => void }) {
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [paying, setPaying] = useState(vip.payment?.status === "REQUESTED" || vip.payment?.status === "REJECTED");

  // "입금했어요"를 누른 뒤에는 30초마다 확인 → VIP가 시작되면 목록 화면으로
  const waiting = vip.payment?.status === "REQUESTED";
  usePolling(
    () => {
      if (!waiting) return;
      api<VipInfo>("/me/vip")
        .then((next) => {
          onChange(next);
          if (next.active) onActivated();
        })
        .catch(() => {});
    },
    30_000,
    [waiting],
  );

  async function request() {
    setError("");
    setSending(true);
    try {
      onChange(await api<VipInfo>("/me/vip/request", { method: "POST" }));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSending(false);
    }
  }

  const benefits = [
    { title: `좋아요 하루 ${vip.base_like_limit}+${vip.daily_like_limit - vip.base_like_limit}개`, body: `기본 이용권은 하루 ${vip.base_like_limit}개예요.` },
    { title: "나를 LIKE한 사람 보기", body: "목록에서 바로 좋아요를 누르면 바로 매칭돼요." },
    { title: `넘긴 사람 ${vip.pass_cooldown_hours}시간 뒤 다시 보기`, body: `기본 이용권은 ${vip.base_pass_cooldown_hours}시간 뒤예요.` },
    { title: `사진 재검토 ${vip.photo_resubmit_days}일마다`, body: `기본 이용권은 ${vip.base_photo_resubmit_days}일마다예요.` },
    { title: "넘겨져도 다음 날 다시 추천", body: "누가 나를 넘겨도 그날 자정까지만 숨겨져요." },
  ];

  return (
    <div className="mx-auto max-w-app">
      <PageTitle eyebrow="VIP" title="받은 LIKE는 VIP에서 볼 수 있어요" />

      <div className="mb-6 rounded-card border border-line bg-paper-card px-6 py-5">
        <p className="text-[13px] text-ink-soft">VIP {vip.days}일 이용권 · 기본 이용권 포함</p>
        <p className="mt-1.5 flex items-baseline gap-2">
          <span className="num font-serif text-[30px] font-semibold">{vip.price.toLocaleString()}원</span>
        </p>
        <p className="mt-2 text-[12.5px] text-ink-faint">자동 결제 없어요. 기간이 끝나면 다시 살 수 있어요.</p>
        {vip.member_days_left ? (
          <p className="mt-1 text-[12.5px] text-ink-soft">
            지금 남은 기본 이용권 <span className="num">{vip.member_days_left}</span>일은 VIP가 끝난 뒤 이어서 쓸 수 있어요.
          </p>
        ) : null}
      </div>

      <ul className="mb-8 space-y-3">
        {benefits.map((b, i) => (
          <li key={b.title} className="flex gap-3">
            <span className="num mt-0.5 text-[13px] font-semibold text-brick">{i + 1}</span>
            <span>
              <span className="block text-[14.5px] font-semibold">{b.title}</span>
              <span className="block text-[13px] text-ink-soft">{b.body}</span>
            </span>
          </li>
        ))}
      </ul>

      {!vip.can_buy || !vip.payment ? (
        <Notice>{vip.blocked_reason ?? "지금은 VIP를 살 수 없어요."}</Notice>
      ) : paying ? (
        <PaymentPanel
          info={vip.payment}
          sending={sending}
          error={error}
          onRequest={request}
          waitingText={`입금 후 15분 이내 확인돼요. 확인되면 ${vip.days}일 뒤 밤 12시까지 VIP예요 (기본 이용권 포함).`}
          refundNote="VIP는 입금이 확인되면 바로 시작돼서 환불되지 않아요."
        />
      ) : (
        <Button size="lg" className="w-full" onClick={() => setPaying(true)}>
          VIP 시작하기 · {vip.price.toLocaleString()}원
        </Button>
      )}
    </div>
  );
}
