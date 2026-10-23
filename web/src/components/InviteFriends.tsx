"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui";
import { api } from "@/lib/api";
import { untilDay } from "@/lib/format";

type Referral = {
  active: boolean;
  start: string | null;
  end: string | null;
  code: string | null;
  invited: number;
  rewarded: number;
  max_rewards: number;
};

const SHARE_TEXT = "학교 메일로 인증한 대학생끼리 쓰는 익명 소개팅 훕팅이야. 사진은 아무한테도 공개 안 돼! 이 링크로 가입해 줘 🙏";

/** 설정 → "친구 초대" (2026-10-24 친구 초대 이벤트). 이벤트 기간에만 보인다.
 *  초대한 친구의 첫 사진이 승인되면 슈퍼 라이크 1개. 친구가 누구인지는 보여주지 않고 숫자만. */
export function InviteFriends() {
  const [r, setR] = useState<Referral | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    api<Referral>("/me/referral")
      .then(setR)
      .catch(() => {});
  }, []);

  if (!r || !r.active || !r.code) return null;
  const link = `${window.location.origin}/?ref=${r.code}`;
  const canShare = typeof navigator !== "undefined" && typeof navigator.share === "function";

  async function copy() {
    try {
      await navigator.clipboard.writeText(link);
    } catch {
      // 복사가 막힌 브라우저: 링크 칸을 길게 눌러 복사
      return;
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  async function share() {
    try {
      await navigator.share({ title: "훕팅", text: SHARE_TEXT, url: link });
    } catch {
      /* 공유 창을 닫은 경우 */
    }
  }

  return (
    <section id="invite" className="mt-14 scroll-mt-20">
      <p className="eyebrow mb-4">친구 초대 이벤트</p>
      <div className="rounded-card border border-brick/30 bg-brick-wash px-5 py-5">
        <p className="text-[16px] font-semibold leading-snug text-ink">
          친구가 내 링크로 가입하면 <span className="text-brick">슈퍼 라이크 1개</span>
        </p>
        <p className="mt-1.5 text-[13.5px] leading-relaxed text-ink-soft">
          외대생·경희대생 누구든 좋아요. 친구의 사진 검수가 끝나면 바로 받아요. 초대 인원 제한 없어요.
          {r.end && <> 이벤트는 {untilDay(r.end)}.</>}
        </p>
        <div className="mt-4 select-all break-all rounded-md border border-line bg-paper-card px-3 py-2.5 text-[14px] text-ink">{link}</div>
        {canShare ? (
          <div className="mt-3 grid grid-cols-2 gap-2">
            <Button variant="secondary" onClick={copy}>
              {copied ? "복사했어요 ✓" : "링크 복사"}
            </Button>
            <Button onClick={share}>공유하기</Button>
          </div>
        ) : (
          <Button className="mt-3 w-full" onClick={copy}>
            {copied ? "복사했어요 ✓" : "링크 복사"}
          </Button>
        )}
        <p className="mt-4 text-[13.5px] text-ink">
          초대로 가입한 친구 <b className="num font-semibold">{r.invited}</b>명 · 받은 슈퍼 라이크{" "}
          <b className="num font-semibold text-brick">{r.rewarded}</b>개
        </p>
        <p className="mt-1 text-[12px] leading-relaxed text-ink-faint">
          친구에게는 누가 초대했는지 보이지 않아요. 탈퇴하고 7일 안에 다시 가입한 계정은 초대로 치지 않아요.
        </p>
      </div>
    </section>
  );
}
