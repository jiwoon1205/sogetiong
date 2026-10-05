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
          <li>🔕 같은 대화방 알림은 10분에 한 번만 오고, 사이트를 보고 있을 때는 오지 않아요.</li>
          <li>📱 아이폰은 사파리에서 &lsquo;홈 화면에 추가&rsquo;한 뒤 그 아이콘으로 열어야 켤 수 있어요.</li>
          <li>✉️ 알림을 켜지 않으면 학교 메일로 알려드려요. (설정에서 끌 수 있어요)</li>
        </ul>
      </>
    ),
    action: { label: "알림 켜러 가기", href: "/settings#alerts" },
  },
};

export function AnnouncementModal({ announcement }: { announcement?: string | null }) {
  const router = useRouter();
  const [closed, setClosed] = useState(false);
  const notice = announcement ? NOTICES[announcement] : undefined;
  if (!announcement || !notice || closed) return null;

  function markSeen() {
    setClosed(true);
    // 실패해도(네트워크 등) 이번에는 닫는다. 다음 접속 때 한 번 더 뜰 수 있다.
    api("/me/announcement/seen", { method: "POST", body: { key: announcement } }).catch(() => {});
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
