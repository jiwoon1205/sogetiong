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
  origin: "LIKE" | "MATCH_IMPORT";
  note: string | null;
  event_count: number;
  blocked_count: number;
  /** 캐주얼(한 번이라도 고른 사람)과 매칭 수 · 그중 이 사람이 먼저 시작한 수 · 슈퍼 라이크로 매칭한 수 */
  casual_matches: number;
  casual_matches_started: number;
  casual_super_likes: number;
  /** 캐주얼에게 보낸 좋아요 수 · 좋아요 보낸 캐주얼 사람 수 */
  casual_likes: number;
  casual_liked_people: number;
  first_at: string;
  last_at: string;
};
type ListData = {
  counts: { WATCHING: number; CLEARED: number };
  totals: { people: number; casual_matches: number; casual_matches_started: number; casual_likes: number; blocked: number };
  targets: Target[];
};
type Detail = {
  person: Person;
  status: string | null;
  origin: string | null;
  note: string | null;
  casual_matches: { at: string; how: string; started: "me" | "them" | null; my_messages: number; status: string; partner: Person }[];
  casual_likes: { count: number; last_at: string; is_super: boolean; partner: Person }[];
  events: { at: string; actor_goal: string | null; is_super: boolean; blocked: boolean; to: Person }[];
};

const SORTS = [
  { value: "recent", label: "최근 순" },
  { value: "matches", label: "캐주얼 매칭 많은 순" },
  { value: "started", label: "먼저 시작한 매칭 많은 순" },
  { value: "likes", label: "캐주얼에게 좋아요 많은 순" },
] as const;

const TABS = [
  { value: "WATCHING", label: "지켜보는 중" },
  { value: "CLEARED", label: "문제없음" },
  { value: "ALL", label: "전체" },
] as const;

const goalLabel = (g: string | null) => (g ? (RELATIONSHIP_LABEL as Record<string, string>)[g] ?? g : "안 고름");

export default function WatchlistPage() {
  const [tab, setTab] = useState<string>("WATCHING");
  const [sort, setSort] = useState<string>("matches");
  const [data, setData] = useState<ListData | null>(null);
  const [open, setOpen] = useState<string | null>(null);

  const load = useCallback(() => {
    adminApi<ListData>(`/watchlist?status=${tab}&sort=${sort}`).then(setData);
  }, [tab, sort]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <>
      <PageTitle
        eyebrow="감시 대상"
        title="캐주얼 상대에게 좋아요를 보낸 사람"
        desc="캐주얼한 만남을 고르지 않았는데 캐주얼한 만남을 고른 사람에게 좋아요·슈퍼 라이크를 보냈거나(막힌 것 포함), 예전에 캐주얼과 매칭된 사람이에요. 숫자는 볼 때마다 새로 세요 (예전 기록 포함). 사용자에게는 절대 보이지 않아요."
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
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        {data && (
          <p className="text-[13px] text-ink-soft">
            <b className="num text-ink">{data.totals.people}</b>명 · 캐주얼 매칭 <b className="num text-ink">{data.totals.casual_matches}</b>
            (먼저 시작 <span className="num">{data.totals.casual_matches_started}</span>) · 캐주얼에게 좋아요{" "}
            <b className="num text-ink">{data.totals.casual_likes}</b> · 막힘 <span className="num">{data.totals.blocked}</span>
          </p>
        )}
        <select
          value={sort}
          onChange={(e) => {
            setSort(e.target.value);
            setData(null);
          }}
          className="rounded-md border border-line bg-paper px-2.5 py-1.5 text-[13px]"
        >
          {SORTS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
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
                {t.origin === "MATCH_IMPORT" && <span className="rounded bg-paper px-1.5 py-0.5 text-[11px] text-ink-faint">예전 매칭으로 추가</span>}
                {t.status === "CLEARED" && <span className="rounded bg-paper px-1.5 py-0.5 text-[11px] text-ink-faint">문제없음</span>}
                <span className="ml-auto flex flex-wrap gap-x-3 text-[12.5px] text-ink-soft">
                  <span>
                    캐주얼 매칭 <b className="num text-brick">{t.casual_matches}</b>
                    <span className="text-ink-faint"> (먼저 {t.casual_matches_started}{t.casual_super_likes > 0 ? ` · 슈퍼 ${t.casual_super_likes}` : ""})</span>
                  </span>
                  <span>
                    좋아요 <b className="num text-brick">{t.casual_likes}</b>
                    <span className="text-ink-faint"> ({t.casual_liked_people}명)</span>
                  </span>
                  {t.blocked_count > 0 && <span className="text-ink-faint">막힘 {t.blocked_count}</span>}
                </span>
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
  const startedLabel = { me: "이 사람이 먼저", them: "캐주얼 쪽이 먼저" } as const;
  return (
    <div className="border-t border-line px-4 py-3">
      <p className="mb-1 text-[12.5px] font-medium text-ink-faint">캐주얼과의 매칭 ({d.casual_matches.length})</p>
      {d.casual_matches.length === 0 ? (
        <p className="mb-3 text-[13px] text-ink-faint">없음</p>
      ) : (
        <ul className="mb-3 space-y-1 text-[13px]">
          {d.casual_matches.map((m, i) => (
            <li key={i} className="flex flex-wrap gap-x-2">
              <span className="num text-ink-faint">{dateTime(m.at)}</span>
              <span className="num">{m.partner.subject_code}</span>
              <span>{m.partner.nickname ?? ""}</span>
              <span className="text-ink-soft">· {m.how}</span>
              <span className={m.started === "me" ? "text-brick" : "text-ink-faint"}>· {m.started ? startedLabel[m.started] : "시작 모름"}</span>
              <span className="text-ink-faint">· 보낸 메시지 {m.my_messages} · {m.status === "ACTIVE" ? "대화 중" : "끝남"}</span>
            </li>
          ))}
        </ul>
      )}
      <p className="mb-1 text-[12.5px] font-medium text-ink-faint">캐주얼에게 보낸 좋아요 ({d.casual_likes.length}명)</p>
      {d.casual_likes.length === 0 ? (
        <p className="mb-3 text-[13px] text-ink-faint">없음</p>
      ) : (
        <ul className="mb-3 space-y-1 text-[13px]">
          {d.casual_likes.map((l, i) => (
            <li key={i} className="flex flex-wrap gap-x-2">
              <span className="num text-ink-faint">{dateTime(l.last_at)}</span>
              <span className="num">{l.partner.subject_code}</span>
              <span>{l.partner.nickname ?? ""}</span>
              <span className="text-brick">· {l.count}번{l.is_super ? " (슈퍼 라이크)" : ""}</span>
            </li>
          ))}
        </ul>
      )}
      <p className="mb-1 text-[12.5px] font-medium text-ink-faint">감시 시작 뒤 기록 ({d.events.length})</p>
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
