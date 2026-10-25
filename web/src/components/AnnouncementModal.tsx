"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, Modal } from "@/components/ui";
import { api } from "@/lib/api";
import { dday, ddayEnd, discountPercent } from "@/lib/format";
import { useSession } from "@/lib/session";
import type { Membership } from "@/lib/types";

type Notice = {
  title: string;
  body: React.ReactNode | ((m: Membership | undefined) => React.ReactNode);
  action?: { label: string; href: string };
  /** 두 번째 버튼 (선택) */
  second?: { label: string; href: string };
  /** 닫기 버튼 문구 */
  close?: string;
};

/** 결제 시스템 오픈 공지 (2026-10-06): 하루 한 번, 정식 배포 전까지. 이름 = "payment-open:YYYY-MM-DD" */
const PAYMENT_OPEN: Notice = {
  title: "이용권 결제가 열렸어요",
  body: (m) => {
    const price = m?.price ?? 3000;
    const regular = m?.regular_price ?? 8000; // 지금 사면 받는 일수 기준 정가 (베타 4주 = 8,000원)
    const afterPrice = m?.price_after_open ?? 4000; // 정식 배포 뒤 가격 (2주)
    const until = m?.discount_until ? ddayEnd(m.discount_until) : "정식 배포 전까지";
    const d = m?.discount_until ? dday(m.discount_until) : null;
    const vipPrice = 6000;
    const days = m?.days ?? 28; // 지금(베타) 사면 받는 일수
    const after = m?.days_after_open ?? 14; // 정식 배포 뒤에 사면 받는 일수
    const weeks = (d: number) => (d % 7 === 0 ? `${d / 7}주` : `${d}일`);
    return (
      <>
        <div className="rounded-card border border-brick/30 bg-brick-wash px-4 py-4 text-center">
          <p className="text-[13px] font-semibold text-brick">
            {d && <span className="mr-1.5 rounded-full bg-brick px-2 py-0.5 text-paper">할인 {d}</span>}
            정식 배포 전에만 {discountPercent(regular, price)}% 할인해요
          </p>
          <p className="mt-1.5 text-[15px] text-ink">
            기본 이용권 {weeks(days)} <s className="text-ink-faint">{regular.toLocaleString()}원</s>{" "}
            <b className="num text-[22px] font-semibold text-brick">{price.toLocaleString()}원</b>
          </p>
          <p className="mt-1 text-[12.5px] text-ink-soft">{until} · 정식 배포 후에는 {weeks(after)} {afterPrice.toLocaleString()}원</p>
        </div>
        <div className="mt-3 rounded-card border border-line bg-paper-card px-4 py-3 text-center">
          <p className="text-[13.5px] leading-relaxed text-ink">
            ⏳ <b className="font-semibold">정식 배포 후에 사면 기간이 {weeks(after)}로 줄어요.</b>
          </p>
          <p className="mt-1 text-[12.5px] text-ink-soft">
            기본 이용권 {afterPrice.toLocaleString()}원 · VIP {vipPrice.toLocaleString()}원이 모두 {weeks(after)}예요. 지금(베타 기간) 사면 {weeks(days)}!
          </p>
        </div>
        <ul className="mt-4 space-y-2 text-[14px] leading-relaxed text-ink-soft">
          <li>
            📅 <b className="font-semibold text-ink">10월 8일 0시 정식 배포</b>부터 이용권이 없으면 <b className="font-semibold text-ink">무료 체험</b>으로 바뀌어요.
            무료 체험 좋아요는 <b className="font-semibold text-brick">평생 3개</b>뿐이에요. 다 쓰면 다음 날에도 <b className="font-semibold text-ink">다시 생기지 않아요.</b>
          </li>
          <li>💸 지금 미리 사도 손해 없어요. {weeks(days)}는 정식 배포 시각부터 세요. 그 전까지는 지금처럼 무료로 써요.</li>
          <li>👑 VIP {weeks(days)} {vipPrice.toLocaleString()}원(기본 포함)은 사는 즉시 바로 시작돼요.</li>
          <li>📸 살 때마다 사진 바로 재검토를 1번 받을 수 있어요.</li>
          <li>💬 이용권이 없어도 추천 보기·넘기기·대화는 계속할 수 있어요.</li>
        </ul>
      </>
    );
  },
  action: { label: "할인가로 미리 사기", href: "/settings#membership" },
  second: { label: "VIP 보기", href: "/liked" },
  close: "오늘은 그만 보기",
};

function findNotice(key: string): Notice | undefined {
  if (key.startsWith("payment-open:")) return PAYMENT_OPEN;
  // 하루 한 번 공지 (2026-10-25): 서버가 "khu-event-2026-10@2026-10-25"처럼 날짜를 붙여 보낸다 → "@" 앞부분으로 찾는다
  return NOTICES[key.split("@")[0]];
}

/** 친구 초대 이벤트 안내 상자 (2026-10-24, 공지 팝업 맨 위). 차분한 바탕 + 큰 글씨 + 3단계, 포인트 색은 글자에만 */
function InviteEventHero() {
  const steps = ["내 초대 링크 복사", "친구가 링크로 가입", "슈퍼 라이크 1개 받기"];
  return (
    <div className="mb-5 overflow-hidden rounded-card border border-line-strong bg-paper-card">
      <div className="px-5 pb-4 pt-5 text-center">
        <p className="inline-block rounded-full border border-brick/25 px-3 py-1 text-[12px] font-semibold tracking-wide text-brick">
          🎁 친구 초대 이벤트 · 11월 6일까지
        </p>
        <p className="mt-3 font-serif text-[23px] font-semibold leading-tight text-ink">
          친구 1명 가입하면
          <br />
          <span className="text-[27px] text-brick">슈퍼 라이크 1개</span>
        </p>
        <p className="mt-2 text-[13px] leading-relaxed text-ink-soft">보내면 상대가 좋아요를 안 눌러도 바로 매칭돼요 (1개 1,000원)</p>
      </div>
      <ol className="grid grid-cols-3 border-t border-line text-center">
        {steps.map((step, i) => (
          <li key={step} className={i > 0 ? "border-l border-line px-2 py-3" : "px-2 py-3"}>
            <span className="num mx-auto flex h-6 w-6 items-center justify-center rounded-full border border-ink/20 text-[12.5px] font-semibold text-ink">
              {i + 1}
            </span>
            <span className="mt-1.5 block text-[12px] leading-snug text-ink-soft">{step}</span>
          </li>
        ))}
      </ol>
      <p className="border-t border-line bg-paper-deep/60 px-4 py-2 text-center text-[12px] text-ink-faint">
        경희대·외대 친구 모두 OK · 인원 제한 없음 · 친구 사진 검수가 끝나면 지급
      </p>
    </div>
  );
}

/**
 * 공지 팝업 (2026-10-05 한 번만, 2026-10-06 하루 한 번 결제 오픈 공지 추가).
 * 서버 /me 의 announcement(아직 안 본 공지 이름)와 아래 NOTICES의 이름이 같을 때만 뜬다.
 * 닫기·확인·"알림 켜러 가기" 어느 것을 눌러도 "봤음"으로 기록 → 이 계정에는 다시 안 뜬다.
 * 새 공지: 서버 services/announcement_service.py 의 CURRENT와 여기 NOTICES에 같은 이름으로 추가.
 */
const NOTICES: Record<string, Notice> = {
  // 경희대 오픈 사전 공지 (2026-10-24). 학교가 하나만 열려 있는 동안 뜬다
  "khu-notice-2026-10": {
    title: "오늘부터 경희대 학생도 함께해요",
    body: (
      <>
        <InviteEventHero />
        <p className="text-[15px] leading-relaxed text-ink">
          <b className="font-semibold">10월 24일(토)</b>부터 <b className="font-semibold">경희대 학생</b>(서울·국제캠퍼스)도 학교 메일 인증을 받고 훕팅을 쓸 수 있어요.
          만날 수 있는 사람이 더 많아져요.
        </p>
        <ul className="mt-4 space-y-2 text-[14px] leading-relaxed text-ink-soft">
          <li>
            🎯 매칭 조건이 <b className="font-semibold text-ink">모든 캠퍼스</b>로 되어 있으면 경희대 학생도 <b className="font-semibold text-ink">자동으로</b> 추천돼요.
          </li>
          <li>
            🙋 외대생만 만나고 싶다면 오픈 전에 <b className="font-semibold text-ink">설정 → 매칭 조건</b>에서 &lsquo;경희대가 열려도 외대생만 만나기&rsquo;를 체크해 주세요. 오픈 뒤에도 언제든 바꿀 수 있어요.
          </li>
          <li>
            🏫 오픈하면 프로필에 <b className="font-semibold text-ink">학교와 캠퍼스가 항상 보여요</b> (지금 캠퍼스를 비공개로 해 둔 분도 공개로 바뀌어요). 학과 공개 여부는 지금처럼 직접 고를 수 있어요.
          </li>
          <li>🔒 사진은 지금처럼 누구에게도 공개되지 않고, 실명·학번도 보이지 않아요.</li>
          <li>🧾 &lsquo;같은 과 제외&rsquo;는 같은 학교의 같은 과에만 적용돼요. 이용권·좋아요 규칙은 그대로예요.</li>
        </ul>
      </>
    ),
    action: { label: "친구 초대 링크 받기", href: "/settings#invite" },
    second: { label: "매칭 조건 보기", href: "/settings#preferences" },
    close: "확인",
  },
  // 경희대 오픈 공지 (2026-10-24). 서버 설정 OPEN_SCHOOLS로 경희대를 열면 자동으로 이 공지로 바뀐다
  // 2026-10-24 새벽: 이벤트를 더 눈에 띄게 바꾸면서 이름을 바꿈 ("khu-open-2026-10" → 이미 본 사람에게도 한 번 더 뜸)
  "khu-event-2026-10": {
    title: "경희대 오픈 기념 친구 초대 이벤트 🎁",
    body: (
      <>
        <InviteEventHero />
        <p className="text-[15px] leading-relaxed text-ink">
          이제 <b className="font-semibold">경희대 학생</b>(서울·국제캠퍼스)도 훕팅을 써요. 추천 카드에 <b className="font-semibold">학교 이름</b>이 함께 보여요.
        </p>
        <ul className="mt-4 space-y-2 text-[14px] leading-relaxed text-ink-soft">
          <li>
            🎯 매칭 조건에서 학교·캠퍼스를 <b className="font-semibold text-ink">모두 체크</b>해 둔 분은 경희대 학생도 추천돼요.
          </li>
          <li>
            🙋 외대생만 만나고 싶다면 <b className="font-semibold text-ink">설정 → 매칭 조건</b>에서 경희대 캠퍼스 체크를 풀어 주세요. 조건은 양쪽 모두 맞아야 추천돼요.
          </li>
          <li>🏫 학교와 캠퍼스는 모든 프로필에 보여요. 학과 공개 여부는 지금처럼 직접 고를 수 있어요.</li>
          <li>🔒 사진은 지금처럼 누구에게도 공개되지 않아요.</li>
        </ul>
      </>
    ),
    action: { label: "친구 초대 링크 받기", href: "/settings#invite" },
    second: { label: "매칭 조건 보기", href: "/settings#preferences" },
    close: "확인",
  },
  "push-alerts-2026-10": {
    title: "휴대폰 알림이 생겼어요 🔔",
    body: (
      <>
        <p className="text-[15px] leading-relaxed text-ink">
          이제 앱 설치 없이 <b className="font-semibold">새 메시지 · 새 매칭</b>을 휴대폰 알림으로 받을 수 있어요.
        </p>
        <ul className="mt-4 space-y-2 text-[14px] leading-relaxed text-ink-soft">
          <li>🔒 잠금화면에는 &lsquo;훕팅 · 새 메시지가 왔어요&rsquo;만 보여요. 상대 닉네임이나 대화 내용은 나오지 않아요.</li>
          <li>💬 카톡처럼 메시지가 올 때마다 알려드려요. 사이트를 보고 있을 때는 오지 않아요.</li>
          <li>📱 아이폰은 사파리에서 &lsquo;홈 화면에 추가&rsquo;한 뒤 그 아이콘으로 열어야 켤 수 있어요.</li>
          <li>✉️ 알림을 켜지 않으면 학교 메일로 알려드려요. (설정에서 끌 수 있어요)</li>
        </ul>
      </>
    ),
    action: { label: "알림 켜러 가기", href: "/settings#alerts" },
  },
};

// "봤음" 기록을 화면 하나(컴포넌트)가 아니라 여기에 둔다 (2026-10-05 수정).
// 예전에는 컴포넌트 안에만 기억해서, 채팅방에 들어갔다 나오면(머리말이 다시 그려지면) 또 떴다.
// /me는 처음 한 번만 받아 오므로 그 안의 announcement 값도 옛날 값 그대로 남아 있기 때문.
const SEEN_KEY = "announcement-seen";
const seenThisVisit = new Set<string>();

function alreadySeen(key: string): boolean {
  if (seenThisVisit.has(key)) return true;
  try {
    return localStorage.getItem(SEEN_KEY) === key; // 서버 기록이 실패했어도 이 기기에서는 다시 안 뜨게
  } catch {
    return false;
  }
}

async function saveSeen(key: string) {
  seenThisVisit.add(key);
  try {
    localStorage.setItem(SEEN_KEY, key);
  } catch {
    /* 저장이 안 되는 브라우저면 서버 기록만 쓴다 */
  }
  // 계정 기준 기록 (다른 기기에서도 안 뜨게). 한 번 실패하면 한 번 더 시도.
  for (let i = 0; i < 2; i++) {
    try {
      await api("/me/announcement/seen", { method: "POST", body: { key } });
      return;
    } catch {
      /* 다시 시도 */
    }
  }
}

export function AnnouncementModal({ announcement }: { announcement?: string | null }) {
  const router = useRouter();
  const { me } = useSession();
  // 닫은 공지 이름을 기억한다 (예전에는 true/false 하나라서, 화면이 열린 채로 새 공지가 와도 안 떴다 — 2026-10-06)
  const [closedKey, setClosedKey] = useState<string | null>(null);
  const notice = announcement ? findNotice(announcement) : undefined;
  if (!announcement || !notice || closedKey === announcement || alreadySeen(announcement)) return null;

  function markSeen() {
    setClosedKey(announcement!);
    void saveSeen(announcement!);
  }

  return (
    <Modal open onClose={markSeen} title={notice.title}>
      {typeof notice.body === "function" ? notice.body(me.membership) : notice.body}
      <div className="mt-6 space-y-2">
        {notice.action && (
          <Button
            className="w-full"
            onClick={() => {
              markSeen();
              router.push(notice.action!.href);
            }}
          >
            {notice.action.label}
          </Button>
        )}
        {notice.second && (
          <Button
            variant="secondary"
            className="w-full"
            onClick={() => {
              markSeen();
              router.push(notice.second!.href);
            }}
          >
            {notice.second.label}
          </Button>
        )}
        <Button variant="ghost" className="w-full" onClick={markSeen}>
          {notice.close ?? (notice.action ? "다음에 할게요" : "확인")}
        </Button>
      </div>
    </Modal>
  );
}
