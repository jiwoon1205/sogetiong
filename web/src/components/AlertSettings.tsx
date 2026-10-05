"use client";

import { useEffect, useState } from "react";
import { Button, Checkbox, Notice } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { PushDenied, currentSubscription, detectEnv, disablePush, enablePush, isIos, permission, type PushEnv } from "@/lib/push";
import type { Alerts } from "@/lib/types";

/**
 * 설정 → 알림 (2026-10-05).
 * 휴대폰 알림 켜기·끄기, 테스트 알림, 기기별 켜는 방법 안내, "메일로 알려주기" 스위치.
 */
export function AlertSettings() {
  const [alerts, setAlerts] = useState<Alerts | null>(null);
  const [env, setEnv] = useState<PushEnv | null>(null);
  const [on, setOn] = useState(false); // 이 기기에서 켜져 있나
  const [denied, setDenied] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ tone: "ok" | "error"; text: string } | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      const [state, sub] = await Promise.all([
        api<Alerts>("/me/alerts").catch(() => null),
        currentSubscription().catch(() => null),
      ]);
      if (!alive) return;
      // 브라우저 기능 확인은 화면이 뜬 뒤(브라우저 안)에서만 할 수 있다
      setEnv(detectEnv());
      setDenied(permission() === "denied");
      setOn(Boolean(sub) && permission() === "granted");
      if (state) setAlerts(state);
    })();
    return () => {
      alive = false;
    };
  }, []);

  // 머리말 안내·메일 링크(/settings#alerts)로 들어오면 이 칸으로 스크롤
  useEffect(() => {
    if (alerts && window.location.hash === "#alerts") {
      document.getElementById("alerts")?.scrollIntoView({ block: "start" });
    }
  }, [alerts]);

  async function turnOn() {
    if (!alerts?.public_key) return;
    setBusy(true);
    setMsg(null);
    try {
      setAlerts(await enablePush(alerts.public_key));
      setOn(true);
      setMsg({ tone: "ok", text: "알림을 켰어요. '테스트 알림 보내기'로 잘 오는지 확인해 보세요." });
    } catch (err) {
      if (err instanceof PushDenied || permission() === "denied") {
        setDenied(true);
      } else {
        setMsg({ tone: "error", text: err instanceof Error && !("status" in err) ? "알림을 켜지 못했어요. 잠시 후 다시 시도해 주세요." : errorMessage(err) });
      }
    } finally {
      setBusy(false);
    }
  }

  async function turnOff() {
    setBusy(true);
    setMsg(null);
    await disablePush();
    setOn(false);
    setAlerts(await api<Alerts>("/me/alerts").catch(() => alerts));
    setBusy(false);
  }

  async function sendTest() {
    setBusy(true);
    setMsg(null);
    try {
      await api("/me/alerts/push/test", { method: "POST" });
      setMsg({ tone: "ok", text: "테스트 알림을 보냈어요. 몇 초 안에 휴대폰에 '알림이 잘 켜졌어요'가 떠요." });
    } catch (err) {
      setMsg({ tone: "error", text: errorMessage(err) });
    } finally {
      setBusy(false);
    }
  }

  async function setEmail(v: boolean) {
    if (!alerts) return;
    setAlerts({ ...alerts, email_notify: v });
    try {
      setAlerts(await api<Alerts>("/me/alerts", { method: "PATCH", body: { email_notify: v } }));
    } catch (err) {
      setAlerts({ ...alerts, email_notify: !v });
      setMsg({ tone: "error", text: errorMessage(err) });
    }
  }

  if (!alerts || !env) return null;

  return (
    <section id="alerts" className="mt-14 scroll-mt-20">
      <p className="eyebrow mb-4">알림</p>
      <div className="rounded-card border border-line bg-paper-card px-5 py-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-[14.5px] font-medium">휴대폰 알림</p>
            <p className="mt-0.5 text-[13px] text-ink-faint">새 메시지 · 새 매칭이 오면 알려드려요</p>
          </div>
          <span className={on ? "text-[13px] font-semibold text-moss" : "text-[13px] text-ink-faint"}>{on ? "켜짐" : "꺼짐"}</span>
        </div>

        <div className="mt-4">
          {!alerts.push_available ? (
            <Notice>휴대폰 알림은 준비 중이에요. 그동안은 학교 메일로 알려드려요.</Notice>
          ) : on ? (
            <div className="flex flex-wrap gap-2">
              <Button size="sm" variant="secondary" onClick={sendTest} loading={busy}>
                테스트 알림 보내기
              </Button>
              <Button size="sm" variant="ghost" onClick={turnOff} disabled={busy}>
                이 기기에서 알림 끄기
              </Button>
            </div>
          ) : denied ? (
            <DeniedGuide />
          ) : env === "ready" ? (
            <>
              {!isIos() && <AndroidGuide />}
              <Button className="w-full" onClick={turnOn} loading={busy}>
                휴대폰 알림 켜기
              </Button>
            </>
          ) : env === "ios-install" ? (
            <IosGuide />
          ) : env === "in-app" ? (
            <InAppGuide />
          ) : (
            <Notice>
              이 브라우저에서는 알림을 켤 수 없어요. 안드로이드는 크롬, 아이폰은 사파리(iOS 16.4 이상)로 열어 주세요.
              {isIos() && " 아이폰이라면 설정 → 일반 → 소프트웨어 업데이트에서 iOS를 최신으로 바꿔 주세요."}
            </Notice>
          )}
        </div>

        {msg && (
          <div className="mt-3">
            <Notice tone={msg.tone}>{msg.text}</Notice>
          </div>
        )}

        {/* 다른 휴대폰(PC에서 보는 중이거나, 친구에게 알려줄 때)용: 기기별 켜는 방법 모아 보기 */}
        {alerts.push_available && !on && (
          <details className="mt-3 text-[13.5px] text-ink-soft">
            <summary className="cursor-pointer select-none text-ink-soft underline underline-offset-2">기기별로 켜는 방법 보기</summary>
            <div className="mt-3 space-y-3">
              <AndroidGuide />
              <IosGuide />
            </div>
          </details>
        )}

        {!on && alerts.device_count > 0 && (
          <p className="mt-3 text-[12.5px] text-ink-faint">다른 기기 {alerts.device_count}대에서는 알림을 받고 있어요.</p>
        )}

        <ul className="mt-4 space-y-1 border-t border-line pt-3 text-[12.5px] leading-relaxed text-ink-faint">
          <li>· 알림에는 &lsquo;훕팅 · 새 메시지가 왔어요&rsquo;만 보여요. 상대 닉네임이나 대화 내용은 잠금화면에 나오지 않아요.</li>
          <li>· 카톡처럼 메시지가 올 때마다 알려드려요. 사이트를 보고 있을 때는 오지 않아요.</li>
          <li>· 로그아웃하면 그 기기에서는 알림이 꺼져요.</li>
        </ul>
      </div>

      <div className="mt-3 rounded-card border border-line bg-paper-card px-5 py-3">
        <Checkbox checked={alerts.email_notify} onChange={setEmail}>
          휴대폰 알림을 못 받을 때 학교 메일로 알려주기
          <span className="mt-0.5 block text-[12.5px] text-ink-faint">알림을 켠 기기가 없으면 새 메시지 · 새 매칭을 메일로 알려드려요.</span>
        </Checkbox>
      </div>
    </section>
  );
}

function Steps({ items }: { items: React.ReactNode[] }) {
  return (
    <ol className="space-y-2 text-[14px] leading-relaxed text-ink-soft">
      {items.map((item, i) => (
        <li key={i} className="flex gap-2.5">
          <span className="num mt-[2px] flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-ink text-[11px] font-semibold text-paper">{i + 1}</span>
          <span>{item}</span>
        </li>
      ))}
    </ol>
  );
}

function AndroidGuide() {
  return (
    <div className="mb-3 rounded-md border border-line bg-paper-deep px-4 py-3">
      <p className="mb-3 text-[14px] font-semibold">안드로이드는 이렇게 켜요</p>
      <Steps
        items={[
          <>
            <b className="font-semibold text-ink">크롬</b> 또는 <b className="font-semibold text-ink">삼성 인터넷</b>으로 private-matching.com 을 열고 로그인해요.
          </>,
          <>
            설정 → 알림 → <b className="font-semibold text-ink">휴대폰 알림 켜기</b>를 눌러요.
          </>,
          <>
            &lsquo;알림을 보내도록 허용할까요?&rsquo;가 뜨면 <b className="font-semibold text-ink">허용</b>을 눌러요.
          </>,
          <>
            <b className="font-semibold text-ink">테스트 알림 보내기</b>로 잘 오는지 확인해요.
          </>,
        ]}
      />
      <p className="mt-3 text-[12.5px] leading-relaxed text-ink-faint">
        앱처럼 쓰고 싶다면: 크롬 오른쪽 위 ⋮ → <b className="font-semibold">홈 화면에 추가</b> (삼성 인터넷은 아래 ≡ → 현재 페이지 추가 → 홈 화면). 알림이 안 오면 휴대폰 설정 → 애플리케이션 → 크롬(또는 훕팅) → 알림이 켜져 있는지 확인해 주세요.
      </p>
    </div>
  );
}

function IosGuide() {
  return (
    <div className="rounded-md border border-line bg-paper-deep px-4 py-3">
      <p className="mb-3 text-[14px] font-semibold">아이폰은 홈 화면에 추가해야 알림을 켤 수 있어요</p>
      <Steps
        items={[
          <>
            <b className="font-semibold text-ink">사파리</b>로 private-matching.com 을 열어요. (iOS 16.4 이상)
          </>,
          <>
            아래쪽 <b className="font-semibold text-ink">공유 버튼</b>(네모에 위쪽 화살표) → <b className="font-semibold text-ink">홈 화면에 추가</b> → 추가
          </>,
          <>
            홈 화면에 생긴 <b className="font-semibold text-ink">훕팅 아이콘</b>으로 열고 로그인해요.
          </>,
          <>
            설정 → 알림 → <b className="font-semibold text-ink">휴대폰 알림 켜기</b> → 허용
          </>,
        ]}
      />
    </div>
  );
}

function InAppGuide() {
  return (
    <div className="rounded-md border border-line bg-paper-deep px-4 py-3">
      <p className="mb-2 text-[14px] font-semibold">카카오톡·에브리타임 안에서 열린 화면이에요</p>
      <p className="text-[14px] leading-relaxed text-ink-soft">
        이 화면에서는 알림을 켤 수 없어요. 화면 위나 아래의 <b className="font-semibold text-ink">메뉴(⋮ 또는 …)</b>에서{" "}
        <b className="font-semibold text-ink">&lsquo;다른 브라우저로 열기&rsquo;</b>를 눌러 안드로이드는 크롬, 아이폰은 사파리로 열어 주세요.
      </p>
    </div>
  );
}

function DeniedGuide() {
  return (
    <div className="rounded-md border border-brick/30 bg-brick-wash px-4 py-3 text-[14px] leading-relaxed text-brick-deep">
      <p className="mb-2 font-semibold">알림이 &lsquo;차단&rsquo;으로 되어 있어요</p>
      {isIos() ? (
        <p>아이폰 설정 앱 → 알림 → 훕팅 → 알림 허용을 켠 뒤, 이 화면을 다시 열어 주세요.</p>
      ) : (
        <p>
          크롬 주소창 왼쪽의 아이콘(또는 ⋮ → 설정 → 사이트 설정) → 알림 → 허용으로 바꾼 뒤 새로고침해 주세요. 홈 화면 아이콘으로 쓰고 있다면 휴대폰 설정 →
          애플리케이션 → 훕팅 → 알림을 켜 주세요.
        </p>
      )}
    </div>
  );
}
