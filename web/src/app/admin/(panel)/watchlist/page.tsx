"use client";

/**
 * 감시 대상 (2026-11-17, 관리자 전용 — 사용자에게는 절대 보이지 않는다).
 * 캐주얼한 만남을 고르지 않은 사람이 캐주얼한 만남을 고른 사람에게 좋아요·슈퍼 라이크를 보내면(막힌 것 포함) 올라온다.
 */
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Button, Notice, PageTitle, Spinner, Textarea } from "@/components/ui";
import { adminApi, useAdmin } from "@/lib/admin";
import { errorMessage } from "@/lib/api";
import { dateTime } from "@/lib/format";
import { GENDER_LABEL, RELATIONSHIP_LABEL } from "@/lib/types";

type Person = {
  user_id: string;
  subject_code: string;
  nickname: string | null;
  gender: string | null;
  relationship_goal: string | null;
  deleted: boolean;
};
type Target = Person & {
  status: "WATCHING" | "CLEARED";
  note: string | null;
  event_count: number;
  blocked_count: number;
  first_at: string;
  last_at: string;
};
type Detail = {
  person: Person;
  status: string | null;
  note: string | null;
  events: { at: string; actor_goal: string | null; is_super: boolean; blocked: boolean; to: Person }[];
};

const TABS = [
  { value: "WATCHING", label: "지켜보는 중" },
  { value: "CLEARED", label: "문제없음" },
  { value: "ALL", label: "전체" },
] as const;

const goalLabel = (g: string | null) => (g ? (RELATIONSHIP_LABEL as Record<string, string>)[g] ?? g : "안 고름");

export default function WatchlistPage() {
  const [tab, setTab] = useState<string>("WATCHING");
  const [data, setData] = useState<{ counts: { WATCHING: number; CLEARED: number }; targets: Target[] } | null>(null);
  const [open, setOpen] = useState<string | null>(null);

  const load = useCallback(() => {
    adminApi<{ counts: { WATCHING: number; CLEARED: number }; targets: Target[] }>(`/watchlist?status=${tab}`).then(setData);
  }, [tab]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <>
      <PageTitle
        eyebrow="감시 대상"
        title="캐주얼 상대에게 좋아요를 보낸 사람"
        desc="캐주얼한 만남을 고르지 않았는데 캐주얼한 만남을 고른 사람에게 좋아요·슈퍼 라이크를 보낸(또는 보내려다 막힌) 사람이에요. 사용자에게는 절대 보이지 않아요."
      />
      <div className="mb-6 flex gap-6 border-b border-line text-[14px]">
        {TABS.map((t) => (
          <button
            key={t.value}
            onClick={() => {
              setTab(t.value);
              setData(null);
              setOpen(null);
            }}
            className={tab === t.value ? "-mb-px border-b-2 border-ink pb-3 font-semibold" : "pb-3 text-ink-faint hover:text-ink"}
          >
            {t.label}
            {data && t.value !== "ALL" && <span className="num ml-1 text-ink-faint">{data.counts[t.value]}</span>}
          </button>
        ))}
      </div>
      {!data ? (
        <Spinner />
      ) : data.targets.length === 0 ? (
        <p className="py-12 text-center text-[14px] text-ink-faint">아직 없어요.</p>
      ) : (
        <div className="space-y-2">
          {data.targets.map((t) => (
            <div key={t.user_id} className="rounded-card border border-line bg-paper-card">
              <button className="flex w-full flex-wrap items-center gap-x-3 gap-y-1 px-4 py-3 text-left" onClick={() => setOpen(open === t.user_id ? null : t.user_id)}>
                <span className="num font-medium text-ink">{t.subject_code}</span>
                <span className="text-[14px] text-ink">{t.nickname ?? "—"}</span>
                <span className="text-[12.5px] text-ink-faint">
                  {t.gender ? GENDER_LABEL[t.gender as keyof typeof GENDER_LABEL] ?? t.gender : ""} · {t.deleted ? "탈퇴" : goalLabel(t.relationship_goal)}
                </span>
                <span className="ml-auto text-[12.5px] text-ink-soft">
                  보낸 횟수 <b className="num text-brick">{t.event_count}</b>
                  {t.blocked_count > 0 && <span className="text-ink-faint"> (막힘 {t.blocked_count})</span>} · 마지막 {dateTime(t.last_at)}
                </span>
                {t.status === "CLEARED" && <span className="rounded bg-paper px-1.5 py-0.5 text-[11px] text-ink-faint">문제없음</span>}
                {t.note && <span className="w-full truncate text-[12.5px] text-ink-soft">메모: {t.note}</span>}
              </button>
              {open === t.user_id && <WatchDetail userId={t.user_id} onChanged={load} />}
            </div>
          ))}
        </div>
      )}
    </>
  );
}

function WatchDetail({ userId, onChanged }: { userId: string; onChanged: () => void }) {
  const admin = useAdmin();
  const [d, setD] = useState<Detail | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    adminApi<Detail>(`/watchlist/${userId}`).then((r) => {
      setD(r);
      setNote(r.note ?? "");
    });
  }, [userId]);

  async function save(status?: "WATCHING" | "CLEARED") {
    setSaving(true);
    setError("");
    try {
      await adminApi(`/watchlist/${userId}`, { method: "PATCH", body: status ? { status, note } : { note } });
      onChanged();
      const r = await adminApi<Detail>(`/watchlist/${userId}`);
      setD(r);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  if (!d) return <div className="px-4 pb-4"><Spinner /></div>;
  return (
    <div className="border-t border-line px-4 py-3">
      <ul className="space-y-1 text-[13px]">
        {d.events.map((e, i) => (
          <li key={i} className="flex flex-wrap gap-x-2">
            <span className="num text-ink-faint">{dateTime(e.at)}</span>
            <span className={e.blocked ? "text-ink-faint" : "text-ink"}>
              {e.blocked ? "막힘" : e.is_super ? "슈퍼 라이크" : "좋아요"} → <span className="num">{e.to.subject_code}</span> {e.to.nickname ?? ""}
            </span>
            <span className="text-ink-faint">(그때 내 찾는 관계: {goalLabel(e.actor_goal)})</span>
          </li>
        ))}
      </ul>
      <div className="mt-3 flex flex-wrap items-center gap-3 text-[13px]">
        <Link href={`/admin/users/${userId}`} className="text-ink underline underline-offset-2">사용자 화면 열기</Link>
      </div>
      {admin.can("users:status") && (
        <div className="mt-3 space-y-2">
          <Textarea rows={2} maxLength={1000} value={note} onChange={(e) => setNote(e.target.value)} placeholder="관리자 메모 (사용자에게 안 보여요)" />
          {error && <Notice tone="error">{error}</Notice>}
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="ghost" loading={saving} onClick={() => save()}>메모 저장</Button>
            {d.status === "WATCHING" ? (
              <Button size="sm" variant="ghost" loading={saving} onClick={() => save("CLEARED")}>문제없음으로</Button>
            ) : (
              <Button size="sm" variant="ghost" loading={saving} onClick={() => save("WATCHING")}>다시 지켜보기</Button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
