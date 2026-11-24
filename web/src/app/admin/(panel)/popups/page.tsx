"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Button, Notice, PageTitle, Spinner } from "@/components/ui";
import { adminApi, useAdmin } from "@/lib/admin";
import { errorMessage } from "@/lib/api";
import { cn, shortSchoolName } from "@/lib/format";

type Data = {
  order: string;
  survey: { open: boolean; votes: number; key: string };
  invite: {
    enabled: boolean;
    schedule: string;
    goal: number;
    seen_today: number;
    lifetime_vip: number;
    active_users: number;
    inviters: number;
    half_way: number;
    top: { user_id: string; nickname: string | null; school: string | null; count: number; done: boolean }[];
  };
  install: {
    enabled: boolean;
    schedule: string;
    seen_3days: number;
    seen_total: number;
    app_users: number;
    active_users: number;
  };
};

/**
 * 공지 팝업 (2026-11-24): 사용자에게 뜨는 팝업의 진행 상황을 보고 켜고 끈다.
 * - 친구 초대 이벤트 (매일) · 앱 설치 안내 (3일에 한 번) · 찬반 투표 (설문 화면에서 관리)
 * - 켜기/끄기는 바로 적용돼요 (다음에 화면을 열 때부터). 기록은 감사 로그에 남아요
 */
export default function PopupsPage() {
  const { can } = useAdmin();
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(
    () =>
      adminApi<Data>("/popups")
        .then((r) => {
          setData(r);
          setError("");
        })
        .catch((e) => setError(errorMessage(e))),
    [],
  );
  useEffect(() => {
    load();
  }, [load]);

  async function toggle(name: "invite" | "install", next: boolean, label: string) {
    const msg = next ? `'${label}' 팝업을 켤까요?\n\n다음에 화면을 여는 사람부터 다시 떠요.` : `'${label}' 팝업을 끌까요?\n\n바로 아무에게도 뜨지 않아요.`;
    if (!window.confirm(msg)) return;
    setBusy(name);
    try {
      await adminApi(`/popups/${name}`, { method: "PUT", body: { enabled: next } });
      await load();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(null);
    }
  }

  if (!data) return error ? <Notice tone="error">{error}</Notice> : <Spinner />;
  const canToggle = can("surveys:manage");
  const { invite, install, survey } = data;
  const pct = (a: number, b: number) => (b ? Math.round((a / b) * 100) : 0);

  return (
    <div className="space-y-8">
      <PageTitle title="공지 팝업" desc={data.order} />
      {error && <Notice tone="error">{error}</Notice>}

      {/* 찬반 투표 */}
      <PopupCard
        title="찬반 투표 (설문)"
        schedule="아직 투표 안 한 사람에게 화면 전체로 · 계정당 한 번"
        on={survey.open}
        right={
          <Link href="/admin/survey" className="inline-flex h-9 items-center rounded-md border border-line-strong px-3.5 text-[13px]">
            설문 화면에서 관리
          </Link>
        }
      >
        <Stat label="투표한 사람" value={`${survey.votes}명`} />
      </PopupCard>

      {/* 친구 초대 이벤트 */}
      <PopupCard
        title={`친구 초대 이벤트 (친구 ${invite.goal}명 → 평생 VIP)`}
        schedule={invite.schedule}
        on={invite.enabled}
        right={
          canToggle && (
            <Button size="sm" variant={invite.enabled ? "danger" : "primary"} loading={busy === "invite"} onClick={() => toggle("invite", !invite.enabled, "친구 초대 이벤트")}>
              {invite.enabled ? "끄기" : "켜기"}
            </Button>
          )
        }
      >
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="오늘 본 사람" value={`${invite.seen_today}명`} hint={`활성 사용자 ${invite.active_users}명`} />
          <Stat label="1명 이상 초대" value={`${invite.inviters}명`} />
          <Stat label={`절반(${Math.floor(invite.goal / 2)}명) 이상`} value={`${invite.half_way}명`} />
          <Stat label="평생 VIP 달성" value={`${invite.lifetime_vip}명`} />
        </div>
        {invite.top.length > 0 && (
          <div className="mt-4">
            <p className="eyebrow mb-2">초대 많이 한 사람</p>
            <ul className="divide-y divide-line rounded-md border border-line">
              {invite.top.map((t) => (
                <li key={t.user_id} className="flex items-center gap-3 px-3 py-2 text-[13.5px]">
                  <Link href={`/admin/users/${t.user_id}`} className="min-w-0 flex-1 truncate underline underline-offset-4">
                    {t.nickname ?? "(프로필 없음)"}
                  </Link>
                  <span className="text-[12px] text-ink-faint">{t.school ? shortSchoolName(t.school) : ""}</span>
                  <div className="h-1.5 w-24 overflow-hidden rounded-full bg-paper-deep">
                    <div className="h-full bg-ink" style={{ width: `${pct(t.count, invite.goal)}%` }} />
                  </div>
                  <span className="num w-12 text-right font-semibold">
                    {t.count}/{invite.goal}
                  </span>
                  {t.done && <span className="text-[12px] text-brick">👑</span>}
                </li>
              ))}
            </ul>
          </div>
        )}
      </PopupCard>

      {/* 앱 설치 안내 */}
      <PopupCard
        title="앱 설치 안내"
        schedule={install.schedule}
        on={install.enabled}
        right={
          canToggle && (
            <Button size="sm" variant={install.enabled ? "danger" : "primary"} loading={busy === "install"} onClick={() => toggle("install", !install.enabled, "앱 설치 안내")}>
              {install.enabled ? "끄기" : "켜기"}
            </Button>
          )
        }
      >
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <Stat label="최근 3일 본 사람" value={`${install.seen_3days}명`} />
          <Stat label="지금까지 본 사람" value={`${install.seen_total}명`} />
          <Stat
            label="앱으로 쓰는 사람"
            value={`${install.app_users}명`}
            hint={`활성 사용자 ${install.active_users}명의 ${pct(install.app_users, install.active_users)}%`}
          />
        </div>
        <p className="mt-3 text-[12px] text-ink-faint">본 사람은 팝업을 닫은 사람 기준이에요 (2026-11-24 배포 뒤부터 쌓임).</p>
      </PopupCard>
    </div>
  );
}

function PopupCard({
  title,
  schedule,
  on,
  right,
  children,
}: {
  title: string;
  schedule: string;
  on: boolean;
  right?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-card border border-line bg-paper-card px-5 py-5">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[16px] font-semibold text-ink">
            {title}
            <span
              className={cn(
                "ml-2 rounded px-1.5 py-0.5 align-middle text-[11.5px] font-semibold",
                on ? "bg-moss/15 text-moss" : "bg-paper-deep text-ink-faint",
              )}
            >
              {on ? "켜짐" : "꺼짐"}
            </span>
          </p>
          <p className="mt-1 text-[12.5px] text-ink-soft">{schedule}</p>
        </div>
        {right}
      </div>
      {children}
    </section>
  );
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-md bg-paper-deep px-3 py-3">
      <p className="text-[12px] text-ink-faint">{label}</p>
      <p className="num mt-0.5 text-[20px] font-semibold text-ink">{value}</p>
      {hint && <p className="text-[11.5px] text-ink-faint">{hint}</p>}
    </div>
  );
}
