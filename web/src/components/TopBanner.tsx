"use client";

import { useEffect, useState } from "react";
import { PushPrompt } from "@/components/PushPrompt";
import { Button, Modal } from "@/components/ui";
import { isInAppBrowser, isIos, isStandalone } from "@/lib/push";
import { kstDay, useKstNewDay } from "@/lib/useKstNewDay";

/** ×를 누른 날짜 (한국 시간 "2026-11-17"). 그날은 숨기고 다음 날 다시 뜬다 (2026-11-17) */
const CLOSED_KEY = "hufting:app-install-banner-closed-day";

function closedToday(): boolean {
  try {
    return localStorage.getItem(CLOSED_KEY) === kstDay();
  } catch {
    return false;
  }
}

/** 안드로이드 크롬·PC 크롬이 주는 "앱 설치" 신호 */
type InstallPromptEvent = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: string }> };

/** 머리말 바로 아래 한 줄.
 *  2026-11-17: 경희대 친구 초대 이벤트 줄 → "훕팅을 앱으로 설치하는 방법" 안내로 바꿨다.
 *  - 앱(홈 화면 아이콘)으로 연 사람에게는 안 보인다. 브라우저로 연 사람은 앱을 설치했는지 알 수 없어서 모두에게 보인다.
 *  - ×를 누르면 오늘(한국 시간)은 숨기고 다음 날 다시 뜬다 = 하루에 한 번.
 *  - 이 줄이 안 보일 때는 원래 자리의 휴대폰 알림 안내(PushPrompt)를 보여준다 (두 줄이 겹치지 않게). */
export function TopBanner() {
  const [installed] = useState(isStandalone);
  const [closed, setClosed] = useState(closedToday);
  const [guideOpen, setGuideOpen] = useState(false);
  const [installEvent, setInstallEvent] = useState<InstallPromptEvent | null>(null);

  // 화면을 켜 둔 채 날짜가 바뀌면 다시 띄운다
  useKstNewDay(() => setClosed(closedToday()));

  useEffect(() => {
    const onPrompt = (e: Event) => {
      e.preventDefault();
      setInstallEvent(e as InstallPromptEvent);
    };
    const onInstalled = () => setClosed(true);
    window.addEventListener("beforeinstallprompt", onPrompt);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onPrompt);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  if (installed || closed) return <PushPrompt />;

  function close() {
    try {
      localStorage.setItem(CLOSED_KEY, kstDay());
    } catch {
      /* 저장이 안 되는 브라우저면 이 화면에서만 숨김 */
    }
    setClosed(true);
  }

  return (
    <div className="border-b border-line bg-paper-deep">
      <div className="mx-auto flex max-w-3xl items-center justify-between gap-3 px-5 py-2.5">
        <button onClick={() => setGuideOpen(true)} className="min-w-0 text-left text-[13.5px] leading-snug text-ink">
          📲 훕팅을 <b className="font-semibold text-brick">앱으로 설치</b>하면 알림도 받고 더 편해요{" "}
          <span className="whitespace-nowrap text-ink-soft underline underline-offset-2">방법 보기</span>
        </button>
        <button onClick={close} aria-label="오늘 하루 숨기기" className="shrink-0 px-1 text-[18px] leading-none text-ink-faint hover:text-ink">
          ×
        </button>
      </div>
      <InstallGuide open={guideOpen} onClose={() => setGuideOpen(false)} installEvent={installEvent} />
    </div>
  );
}

function InstallGuide({ open, onClose, installEvent }: { open: boolean; onClose: () => void; installEvent: InstallPromptEvent | null }) {
  const ios = isIos();
  const inApp = isInAppBrowser();

  async function installNow() {
    if (!installEvent) return;
    await installEvent.prompt();
    onClose();
  }

  return (
    <Modal open={open} onClose={onClose} title="훕팅을 앱으로 설치하기">
      <div className="space-y-4 text-[14px] leading-relaxed text-ink">
        <p className="text-ink-soft">
          스토어에서 받지 않아도 돼요. 홈 화면에 훕팅 아이콘이 생기고, 앱처럼 전체 화면으로 열려요. <b className="font-semibold text-ink">새 매칭·메시지 알림</b>도
          받을 수 있어요.
        </p>

        {inApp && (
          <p className="rounded-md border border-brick/30 bg-brick-wash px-3 py-2.5 text-[13.5px] text-brick-deep">
            지금 카카오톡·인스타그램·에브리타임 같은 앱 안에서 열려 있어요. 오른쪽 위(또는 아래) 메뉴에서{" "}
            <b className="font-semibold">{ios ? "‘Safari로 열기’" : "‘다른 브라우저로 열기’"}</b>를 누른 뒤 아래 방법대로 해 주세요.
          </p>
        )}

        {installEvent && !ios && (
          <Button className="w-full" onClick={installNow}>
            지금 바로 설치하기
          </Button>
        )}

        <Guide title="아이폰 (Safari)" highlight={ios}>
          <li>
            <b className="font-semibold">Safari</b>로 훕팅을 열어요 (크롬·네이버 앱에서는 안 돼요)
          </li>
          <li>
            아래쪽 가운데 <b className="font-semibold">공유 버튼</b>(네모에 위쪽 화살표 ⬆︎)을 눌러요
          </li>
          <li>
            목록을 내려 <b className="font-semibold">‘홈 화면에 추가’</b> → 오른쪽 위 <b className="font-semibold">‘추가’</b>
          </li>
          <li>홈 화면의 훕팅 아이콘으로 열면 끝!</li>
        </Guide>

        <Guide title="안드로이드 (크롬)" highlight={!ios}>
          <li>
            <b className="font-semibold">크롬</b>으로 훕팅을 열어요
          </li>
          <li>
            오른쪽 위 <b className="font-semibold">⋮</b> → <b className="font-semibold">‘앱 설치’</b> 또는 <b className="font-semibold">‘홈 화면에 추가’</b>
          </li>
          <li>
            삼성 인터넷이라면 아래쪽 <b className="font-semibold">≡</b> → <b className="font-semibold">‘현재 페이지 추가’</b> → <b className="font-semibold">‘홈 화면’</b>
          </li>
          <li>홈 화면의 훕팅 아이콘으로 열면 끝!</li>
        </Guide>

        <p className="text-[12.5px] text-ink-faint">이미 설치했다면 홈 화면의 훕팅 아이콘으로 열어 주세요. 아이콘으로 열면 이 안내가 더 이상 안 보여요.</p>
      </div>
    </Modal>
  );
}

function Guide({ title, highlight, children }: { title: string; highlight: boolean; children: React.ReactNode }) {
  return (
    <div className={`rounded-md border px-3.5 py-3 ${highlight ? "border-ink/40 bg-paper-card" : "border-line"}`}>
      <p className="mb-1.5 text-[13.5px] font-semibold text-ink">{title}</p>
      <ol className="list-decimal space-y-1 pl-5 text-[13.5px] text-ink-soft">{children}</ol>
    </div>
  );
}
