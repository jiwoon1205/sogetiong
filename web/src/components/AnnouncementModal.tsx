"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, Modal } from "@/components/ui";
import { api } from "@/lib/api";

/**
 * 한 번만 보여주는 공지 팝업 (2026-10-05).
 * 서버 /me 의 announcement(아직 안 본 공지 이름)와 아래 NOTICES의 이름이 같을 때만 뜬다.
 * 닫기·확인·"알림 켜러 가기" 어느 것을 눌러도 "봤음"으로 기록 → 이 계정에는 다시 안 뜬다.
 * 새 공지: 서버 services/announcement_service.py 의 CURRENT와 여기 NOTICES에 같은 이름으로 추가.
 */
const NOTICES: Record<string, { title: string; body: React.ReactNode; action?: { label: string; href: string } }> = {
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
  const [closed, setClosed] = useState(() => (announcement ? alreadySeen(announcement) : true));
  const notice = announcement ? NOTICES[announcement] : undefined;
  if (!announcement || !notice || closed) return null;

  function markSeen() {
    setClosed(true);
    void saveSeen(announcement!);
  }

  return (
    <Modal open onClose={markSeen} title={notice.title}>
      {notice.body}
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
        <Button variant="ghost" className="w-full" onClick={markSeen}>
          {notice.action ? "다음에 할게요" : "확인"}
        </Button>
      </div>
    </Modal>
  );
}
