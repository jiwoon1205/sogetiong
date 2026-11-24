"use client";

import { useEffect, useState } from "react";
import { Button, Modal } from "@/components/ui";
import { api } from "@/lib/api";
import { hadOtherPopup, markOtherPopup } from "@/lib/popupGate";
import { isInAppBrowser, isIos, isStandalone } from "@/lib/push";
import type { Me } from "@/lib/types";

/**
 * 앱 설치 안내 팝업 (2026-11-24).
 * - 브라우저로 연 사람에게만 (앱=홈 화면 아이콘으로 열면 절대 안 뜸)
 * - 이번에 열었을 때 다른 팝업(설문·찾는 관계·공지·친구 초대 이벤트·매칭 팁)이 하나라도 있으면 안 뜬다
 *   → 다른 팝업을 닫고 다음에 들어왔을 때, 더 나올 팝업이 없으면 그때 뜬다
 * - "다음에 할게요"/× → 3일 동안 안 뜸
 * - 아이폰 / 안드로이드에 맞는 설치 방법. 안드로이드 크롬은 [지금 바로 설치하기] 한 번
 *
 * 앱으로 열렸으면 서버에 알린다 (/me/app-open) → 관리자 현황 "앱으로 쓰는 사람"
 */
const DISMISSED_KEY = "hufting:install-popup-dismissed-at";
const REST_DAYS = 3;

type InstallPromptEvent = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: string }> };

let reported = false;

function platform(): "IOS" | "ANDROID" | "DESKTOP" {
  if (isIos()) return "IOS";
  if (/Android/i.test(navigator.userAgent)) return "ANDROID";
  return "DESKTOP";
}

function restedEnough(): boolean {
  try {
    const at = Number(localStorage.getItem(DISMISSED_KEY) || 0);
    return Date.now() - at > REST_DAYS * 24 * 60 * 60 * 1000;
  } catch {
    return true;
  }
}

export function InstallPopup({ me }: { me: Me }) {
  // 이번에 열었을 때 한 번만 판단한다 (공지를 닫아도 같은 접속에서는 이어서 뜨지 않게)
  const [open, setOpen] = useState(() => {
    if (typeof window === "undefined" || isStandalone() || me.install_popup === false) return false;
    if (hadOtherPopup() || me.announcement || me.match_tip) {
      markOtherPopup();
      return false;
    }
    if (!restedEnough()) return false;
    markOtherPopup(); // 이번 접속에서는 이 팝업이 하나
    return true;
  });
  const [installEvent, setInstallEvent] = useState<InstallPromptEvent | null>(null);

  // 앱으로 열렸으면 서버에 알림 (페이지를 열 때 한 번)
  useEffect(() => {
    if (reported || !isStandalone()) return;
    reported = true;
    void api("/me/app-open", { method: "POST", body: { platform: platform() } }).catch(() => {});
  }, []);

  useEffect(() => {
    const onPrompt = (e: Event) => {
      e.preventDefault();
      setInstallEvent(e as InstallPromptEvent);
    };
    window.addEventListener("beforeinstallprompt", onPrompt);
    return () => window.removeEventListener("beforeinstallprompt", onPrompt);
  }, []);

  function close() {
    try {
      localStorage.setItem(DISMISSED_KEY, String(Date.now()));
    } catch {}
    setOpen(false);
    // 관리자 → 공지 팝업 진행 상황용 기록
    void api("/me/install-popup/seen", { method: "POST" }).catch(() => {});
  }

  async function installNow() {
    if (!installEvent) return;
    await installEvent.prompt();
    close();
  }

  if (!open) return null;
  const ios = isIos();
  const inApp = isInAppBrowser();

  return (
    <Modal open onClose={close} title="훕팅을 앱으로 쓰세요">
      <div className="space-y-4 text-[14px] leading-relaxed text-ink">
        <p className="rounded-md bg-paper-deep px-4 py-3 text-[13.5px] text-ink-soft">
          스토어 설치 없이 홈 화면에 훕팅 아이콘이 생겨요. <b className="font-semibold text-ink">새 매칭·메시지 알림</b>
          {ios ? "을 받을 수 있어요 (아이폰은 앱으로 열어야만 알림이 와요)." : "을 놓치지 않아요."}
        </p>

        {inApp && (
          <p className="rounded-md border border-brick/30 bg-brick-wash px-3 py-2.5 text-[13.5px] text-brick-deep">
            지금 카카오톡·인스타그램·에브리타임 같은 앱 안에서 열려 있어요. 오른쪽 위(또는 아래) 메뉴에서{" "}
            <b className="font-semibold">{ios ? "‘Safari로 열기’" : "‘다른 브라우저로 열기’"}</b>를 누른 뒤 아래 방법대로 해 주세요.
          </p>
        )}

        {!ios && installEvent && (
          <Button className="w-full" size="lg" onClick={installNow}>
            지금 바로 설치하기
          </Button>
        )}

        {ios ? (
          <ol className="space-y-2.5">
            <Step n={1}>
              화면 아래 <b className="font-semibold">공유 버튼</b>(네모에 위쪽 화살표 ⬆︎)을 눌러요
            </Step>
            <Step n={2}>
              아래로 내려서 <b className="font-semibold">‘홈 화면에 추가’</b> → 오른쪽 위 <b className="font-semibold">‘추가’</b>
            </Step>
            <Step n={3}>
              홈 화면의 <b className="font-semibold">훕팅 아이콘</b>으로 열고 로그인해요
            </Step>
          </ol>
        ) : (
          <>
            {installEvent && <p className="text-[12.5px] text-ink-faint">버튼이 안 되면:</p>}
            <ol className="space-y-2.5">
              <Step n={1}>
                크롬 오른쪽 위 <b className="font-semibold">⋮</b> 메뉴
              </Step>
              <Step n={2}>
                <b className="font-semibold">‘홈 화면에 추가’</b>(또는 ‘앱 설치’) → 설치
              </Step>
              <Step n={3}>
                삼성 인터넷: 아래 <b className="font-semibold">≡</b> → ‘현재 페이지 추가’ → ‘홈 화면’
              </Step>
            </ol>
          </>
        )}

        <div className="space-y-2 pt-1">
          {ios && (
            <Button className="w-full" onClick={close}>
              알겠어요
            </Button>
          )}
          <button type="button" onClick={close} className="w-full py-2 text-center text-[13.5px] text-ink-soft hover:text-ink">
            다음에 할게요
          </button>
        </div>
      </div>
    </Modal>
  );
}

function Step({ n, children }: { n: number; children: React.ReactNode }) {
  return (
    <li className="flex gap-3">
      <span className="num flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-ink/20 text-[12.5px] font-semibold">{n}</span>
      <span>{children}</span>
    </li>
  );
}
