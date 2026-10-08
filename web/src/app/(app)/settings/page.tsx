"use client";

import { DiscountTag, SalePrice } from "@/components/DiscountTag";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AlertSettings } from "@/components/AlertSettings";
import { BusinessInfo } from "@/components/BusinessInfo";
import { MembershipRenew, OPEN_PAY_KEY } from "@/components/PaymentStep";
import { PreferencesForm } from "@/components/PreferencesForm";
import { SupportContact } from "@/components/SupportContact";
import { Button, Field, Input, Modal, Notice, PageTitle, Spinner } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { useCatalog } from "@/lib/catalog";
import { untilDay } from "@/lib/format";
import { disablePush } from "@/lib/push";
import { useSession } from "@/lib/session";

export default function SettingsPage() {
  const router = useRouter();
  const { me, refresh } = useSession();
  const { campuses, loaded } = useCatalog(me.university_id);
  const [deleteOpen, setDeleteOpen] = useState(false);

  async function logout() {
    // 이 기기의 휴대폰 알림도 끈다 (다른 사람이 이 기기로 로그인해도 내 알림이 오지 않게)
    await disablePush().catch(() => {});
    await api("/auth/logout", { method: "POST" }).catch(() => {});
    router.replace("/");
  }

  if (!loaded) return <Spinner />;

  return (
    <div className="mx-auto max-w-app">
      <PageTitle eyebrow="설정" title="매칭 조건" desc="바꾼 조건은 다음 추천부터 반영돼요." />
      <PreferencesForm campuses={campuses} />

      <MyMembership onActivated={() => void refresh()} />

      <AlertSettings />

      <section className="mt-14">
        <p className="eyebrow mb-4">계정</p>
        <div className="divide-y divide-line rounded-card border border-line bg-paper-card">
          <div className="flex items-center justify-between px-5 py-4">
            <div>
              <p className="text-[13px] text-ink-faint">학교 이메일 · 나만 볼 수 있어요</p>
              <p className="mt-0.5 text-[14.5px]">{me.email}</p>
            </div>
          </div>
          <button onClick={logout} className="block w-full px-5 py-4 text-left text-[14.5px] hover:bg-paper-deep/60">
            로그아웃
          </button>
          <button onClick={() => setDeleteOpen(true)} className="block w-full px-5 py-4 text-left text-[14.5px] text-brick hover:bg-brick-wash/50">
            탈퇴하기
          </button>
        </div>
        <p className="mt-4 text-[13px] leading-relaxed text-ink-faint">
          학과 변경, 불편한 점, 그 밖의 문의는 메일로 보내주세요. <SupportContact prefix="" />
        </p>
        <BusinessInfo className="mt-8" />
        {/* 지금 보고 있는 화면이 어느 커밋으로 만든 것인지 (배포가 제대로 됐는지 확인용) */}
        <p className="mt-8 text-center text-[11.5px] text-ink-faint">
          버전 <span className="font-mono">{process.env.NEXT_PUBLIC_APP_VERSION || "dev"}</span>
        </p>
      </section>

      <DeleteAccount open={deleteOpen} onClose={() => setDeleteOpen(false)} onDone={() => router.replace("/")} />
    </div>
  );
}

/** 내 이용권 (2026-10-04 구독제): 남은 기간 + 미리 연장. 판매 전·테스트 계정은 안 보인다.
 *  2026-10-06: 유료 시작 전에도 판매 중이면 보인다 (미리 사기), 무료 체험 좋아요 남은 개수도 보여준다. */
function MyMembership({ onActivated }: { onActivated: () => void }) {
  // 체험 좋아요를 다 쓴 알림창의 "이용권 사러 가기"로 들어오면 결제창을 바로 펼친다 (2026-10-08)
  const [autoPay] = useState(() => {
    try {
      return sessionStorage.getItem(OPEN_PAY_KEY) === "1";
    } catch {
      return false;
    }
  });
  useEffect(() => {
    if (!autoPay) return;
    try {
      sessionStorage.removeItem(OPEN_PAY_KEY);
    } catch {
      /* 저장소를 못 쓰는 브라우저 */
    }
    document.getElementById("membership")?.scrollIntoView({ block: "start" });
  }, [autoPay]);
  const { me } = useSession();
  const m = me.membership;
  if (!m || !(m.sales_open ?? m.enabled) || m.free) return null;
  const vipUntil = me.vip?.active ? me.vip.until : null;
  let line: string;
  if (m.status === "active" && m.until) line = `${untilDay(m.until)} · ${m.days_left}일 남음`;
  else if (m.status === "banked") line = `사진 검수가 끝나 추천이 열리는 날부터 ${m.banked_days}일 이용할 수 있어요.`;
  else if (m.status === "expired") line = "이용권이 끝났어요. 추천 보기·넘기기·대화는 계속할 수 있어요.";
  else if (m.before_open) line = "아직 이용권이 없어요. 지금은 무료 베타 기간이에요.";
  else if (m.trial && m.trial.left > 0) line = `무료 체험 중 · 좋아요 ${m.trial.left}/${m.trial.limit}개 남음 (다시 생기지 않아요)`;
  else line = "무료 체험 좋아요를 모두 사용했어요. 추천 보기·넘기기·대화는 계속할 수 있어요.";
  return (
    <section id="membership" className="mt-14 scroll-mt-20">
      <p className="eyebrow mb-4">내 이용권</p>
      <div className="mb-4 rounded-card border border-line bg-paper-card px-5 py-4">
        <p className="text-[13px] text-ink-faint">
          기본 이용권 {m.days}일 <SalePrice m={m} strikeClass="text-ink-faint" priceClass="text-brick" />
        </p>
        <DiscountTag m={m} className="mt-1" />
        <p className="mt-0.5 text-[14.5px]">{line}</p>
        {vipUntil && <p className="mt-2 text-[13.5px] text-brick">VIP {untilDay(vipUntil)}</p>}
      </div>
      {m.status !== "banked" && <MembershipRenew onActivated={onActivated} autoOpen={autoPay} />}
      <p className="mt-3 text-[12.5px] leading-relaxed text-ink-faint">
        자동 결제는 없어요. 남은 기간이 있을 때 미리 사면 끝나는 날 뒤에 {m.days}일이 더해져요. 살 때마다 사진 바로 재검토를 1번 받을 수 있어요 (쌓이지 않아요). 연장 결제는 입금 확인 후 환불되지 않아요.
      </p>
    </section>
  );
}

function DeleteAccount({ open, onClose, onDone }: { open: boolean; onClose: () => void; onDone: () => void }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await api("/me", { method: "DELETE", body: { password } });
      onDone();
    } catch (err) {
      setError(errorMessage(err));
      setLoading(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="탈퇴하기">
      <form onSubmit={submit} className="space-y-4">
        <p className="text-[14.5px] font-semibold text-brick">탈퇴하면 되돌릴 수 없어요.</p>
        <ul className="list-disc space-y-1.5 pl-5 text-[14px] leading-relaxed text-ink-soft">
          <li>다른 사람에게는 바로 보이지 않아요. 프로필, 관심사, 매칭 조건은 신고 확인을 위해 7일 동안 보관한 뒤 자동으로 삭제돼요.</li>
          <li>진행 중인 대화는 모두 끝나요. 다시 가입해도 예전 매칭·대화는 돌아오지 않아요.</li>
          <li>생년월일·실명·학번 등 가입 정보와 채팅·신고 기록은 분쟁·신고 처리를 위해 일정 기간 보관한 뒤 삭제돼요.</li>
        </ul>
        {/* 2026-10-05: 탈퇴 후 바로 재가입 가능. 대신 점수·재검토 대기·이용권은 이어진다 (auth_service.carry_over_account) */}
        <p className="text-[13px] leading-relaxed text-ink-faint">
          같은 학교 메일로 <b className="font-semibold text-ink-soft">언제든 다시 가입</b>할 수 있어요. 다시 가입하면 사진 평가 점수, 사진 재검토 대기 기간, 남은 이용권·VIP 기간, 무료 체험 좋아요 사용 개수는 그대로 이어져요. 차단했던 상대는 다시 가입해도 계속 차단돼요.
        </p>
        <Field label="비밀번호 확인" htmlFor="del-pw">
          <Input id="del-pw" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </Field>
        {error && <Notice tone="error">{error}</Notice>}
        <Button type="submit" variant="danger" className="w-full" loading={loading}>
          탈퇴하기
        </Button>
      </form>
    </Modal>
  );
}
