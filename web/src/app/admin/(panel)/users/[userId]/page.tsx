"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ProfileCard } from "@/components/ProfileCard";
import { Button, Field, Input, Notice, Segmented, Spinner } from "@/components/ui";
import { USER_STATUS_LABEL, adminApi, useAdmin } from "@/lib/admin";
import { errorMessage } from "@/lib/api";
import { dateTime } from "@/lib/format";
import type { Card } from "@/lib/types";

type Detail = {
  user_id: string;
  subject_code: string;
  status: string;
  created_at: string;
  profile: Card | null;
  reports_received: number;
  deleted_at: string | null;
  linked_accounts: { user_id: string; subject_code: string; status: string; created_at: string; deleted_at: string | null }[];
  private?: { email: string; real_name: string | null; phone_number: string | null; student_id: string | null; birth_date: string };
};

export default function UserDetail() {
  const { userId } = useParams<{ userId: string }>();
  const admin = useAdmin();
  const [d, setD] = useState<Detail | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(
    (includePrivate = false) =>
      adminApi<Detail>(`/users/${userId}${includePrivate ? "?include_private=true" : ""}`)
        .then(setD)
        .catch((e) => setError(errorMessage(e))),
    [userId],
  );

  useEffect(() => {
    load();
  }, [load]);

  if (!d) return error ? <Notice tone="error">{error}</Notice> : <Spinner />;

  return (
    <>
      <Link href="/admin/users" className="text-[13px] text-ink-soft hover:text-ink">
        ← 사용자 목록
      </Link>
      <div className="mb-8 mt-3 flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <h1 className="font-mono text-[26px] font-semibold tracking-wide">{d.subject_code}</h1>
        <p className="text-[13px] text-ink-faint">
          {dateTime(d.created_at)} 가입{d.deleted_at && <> · {dateTime(d.deleted_at)} 탈퇴</>} · {USER_STATUS_LABEL[d.status] ?? d.status} · 받은 신고 <span className="num">{d.reports_received}</span>건
        </p>
      </div>

      <div className="grid gap-8 lg:grid-cols-[minmax(0,24rem)_1fr]">
        <div>{d.profile ? <ProfileCard card={d.profile} /> : <Notice>공개 프로필이 없습니다 (탈퇴 등).</Notice>}</div>
        <div className="space-y-10">
          {admin.can("users:status") && (
            <StatusForm key={d.user_id} userId={d.user_id} current={d.status} deleted={!!d.deleted_at} onDone={() => load(!!d.private)} />
          )}

          {admin.can("chats:read") && <UserChats userId={d.user_id} />}

          {d.linked_accounts.length > 0 && (
            <section>
              <p className="eyebrow mb-3">같은 학교 메일로 가입했던 계정</p>
              <ul className="divide-y divide-line rounded-card border border-line bg-paper-card text-[14px]">
                {d.linked_accounts.map((a) => (
                  <li key={a.user_id} className="flex flex-wrap items-baseline justify-between gap-2 px-5 py-3">
                    <Link href={`/admin/users/${a.user_id}`} className="font-mono font-semibold underline underline-offset-4">
                      {a.subject_code}
                    </Link>
                    <span className="text-[13px] text-ink-faint">
                      {dateTime(a.created_at)} 가입{a.deleted_at && <> · {dateTime(a.deleted_at)} 탈퇴</>} · {USER_STATUS_LABEL[a.status] ?? a.status}
                    </span>
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-[12.5px] text-ink-faint">탈퇴 후 재가입한 경우예요. 제재가 필요하면 각 계정마다 따로 처리하세요.</p>
            </section>
          )}

          {admin.can("users:private:read") && (
            <section>
              <p className="eyebrow mb-3">개인정보</p>
              {d.private ? (
                <dl className="divide-y divide-line rounded-card border border-line bg-paper-card text-[14px]">
                  {[
                    ["이메일", d.private.email],
                    ["실명", d.private.real_name],
                    ["학번", d.private.student_id],
                    ["전화번호", d.private.phone_number],
                    ["생년월일", d.private.birth_date],
                  ].map(([k, v]) => (
                    <div key={k} className="grid grid-cols-[6rem_1fr] px-5 py-3">
                      <dt className="text-ink-faint">{k}</dt>
                      <dd>{v ?? "—"}</dd>
                    </div>
                  ))}
                </dl>
              ) : (
                <div className="space-y-3">
                  <Notice>열람하면 감사 로그에 기록됩니다. 신고 처리 등 꼭 필요한 경우에만 여세요.</Notice>
                  <Button variant="secondary" onClick={() => load(true)}>
                    개인정보 열람
                  </Button>
                </div>
              )}
            </section>
          )}
        </div>
      </div>
    </>
  );
}

type MatchRow = {
  match_id: string;
  partner: { user_id: string; subject_code: string; nickname: string | null };
  status: string;
  matched_at: string;
  ended_at: string | null;
  message_count: number;
  last_message_at: string | null;
};

const MATCH_STATUS_LABEL: Record<string, string> = { ACTIVE: "대화 중", UNMATCHED: "매칭 해제", BLOCKED: "차단으로 종료" };

/** 이 사용자의 모든 대화방 (목록만. 내용은 눌러서 열면 감사 로그에 기록됨) */
function UserChats({ userId }: { userId: string }) {
  const [rows, setRows] = useState<MatchRow[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    adminApi<{ matches: MatchRow[] }>(`/users/${userId}/matches`)
      .then((r) => setRows(r.matches))
      .catch((e) => setError(errorMessage(e)));
  }, [userId]);

  return (
    <section>
      <p className="eyebrow mb-3">대화</p>
      {error ? (
        <Notice tone="error">{error}</Notice>
      ) : !rows ? (
        <Spinner />
      ) : rows.length === 0 ? (
        <p className="text-[13.5px] text-ink-faint">매칭된 상대가 없어요.</p>
      ) : (
        <ul className="divide-y divide-line rounded-card border border-line bg-paper-card text-[14px]">
          {rows.map((m) => (
            <li key={m.match_id} className="flex flex-wrap items-baseline justify-between gap-2 px-5 py-3">
              <span>
                <span className="font-mono">{m.partner.subject_code}</span>
                <span className="text-ink-soft"> · {m.partner.nickname ?? "(탈퇴)"}</span>
                <span className="ml-2 text-[12.5px] text-ink-faint">
                  {MATCH_STATUS_LABEL[m.status] ?? m.status} · 메시지 <span className="num">{m.message_count}</span>개
                  {m.last_message_at && <> · 마지막 {dateTime(m.last_message_at)}</>}
                </span>
              </span>
              <Link href={`/admin/chats/${m.match_id}`} className="text-[13px] underline underline-offset-4">
                대화 보기
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

type Status = "ACTIVE" | "SUSPENDED" | "BANNED" | "DELETED";

function StatusForm({ userId, current, deleted, onDone }: { userId: string; current: string; deleted: boolean; onDone: () => void }) {
  const [status, setStatus] = useState<Status>(current as Status);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [ok, setOk] = useState(false);
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    setOk(false);
    try {
      await adminApi(`/users/${userId}/status`, { method: "PATCH", body: { status, reason } });
      setOk(true);
      setReason("");
      onDone();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <p className="eyebrow">계정 상태</p>
      <Segmented
        value={status}
        onChange={setStatus}
        options={
          deleted
            ? [
                { value: "DELETED", label: "탈퇴 (재가입 가능)" },
                { value: "BANNED", label: "영구 정지 (재가입 차단)" },
              ]
            : [
                { value: "ACTIVE", label: "정상" },
                { value: "SUSPENDED", label: "일시 정지" },
                { value: "BANNED", label: "영구 정지" },
              ]
        }
      />
      <Field label="사유 (감사 로그에 남아요)" htmlFor="status-reason">
        <Input id="status-reason" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} placeholder="신고 누적 (성희롱 2건)" />
      </Field>
      {deleted ? (
        <p className="text-[12.5px] text-ink-faint">탈퇴한 계정이에요. 영구 정지하면 같은 학교 메일로 다시 가입할 수 없어요.</p>
      ) : (
        status !== "ACTIVE" && <p className="text-[12.5px] text-ink-faint">정지하면 해당 사용자는 즉시 로그아웃돼요.</p>
      )}
      {error && <Notice tone="error">{error}</Notice>}
      {ok && <Notice tone="ok">변경했어요.</Notice>}
      <Button type="submit" variant={status === "ACTIVE" || status === "DELETED" ? "primary" : "danger"} loading={loading} disabled={status === current || reason.trim().length < 2}>
        상태 변경
      </Button>
    </form>
  );
}
