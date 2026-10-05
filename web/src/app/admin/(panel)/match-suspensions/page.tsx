"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Button, Notice, PageTitle, Spinner } from "@/components/ui";
import { USER_STATUS_LABEL, adminApi } from "@/lib/admin";
import { errorMessage } from "@/lib/api";
import { dateTime } from "@/lib/format";

type Person = { user_id: string; subject_code: string; nickname: string | null };

type SuspendedUser = Person & {
  status: string;
  match_suspended_at: string | null;
  hidden_matches: number;
  /** 하루 매칭 3번으로 서버가 자동으로 건 정지인가 (2026-10-06) */
  auto_suspended: boolean;
  suspend_reason: string | null;
};

type HiddenMatch = {
  match_id: string;
  members: (Person & { match_suspended: boolean })[];
  hidden_at: string;
  /** 다시 보이게 할 수 없는 이유 (탈퇴·정지·차단). null이면 가능 */
  reveal_blocked_reason: string | null;
};

type Data = { users: SuspendedUser[]; hidden_matches: HiddenMatch[] };

/**
 * 매칭 정지된 사용자 (2026-10-05)
 * - 위: 지금 매칭 정지 중인 사람. 정지를 풀려면 사용자 상세 화면에서 푼다.
 * - 아래: 숨겨진 매칭 전체 (정지를 이미 푼 사람 것도 포함). 하나씩 골라 "다시 보이게" 한다.
 */
export default function MatchSuspensionsPage() {
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [done, setDone] = useState("");

  const load = useCallback(
    () =>
      adminApi<Data>("/match-suspensions")
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

  async function reveal(m: HiddenMatch) {
    const names = m.members.map((p) => p.nickname ?? p.subject_code).join(" · ");
    if (!window.confirm(`${names}\n\n이 매칭을 두 사람에게 보이게 할까요? 두 사람 모두에게 "새로운 매칭" 알림이 가요.`)) return;
    setBusy(m.match_id);
    setError("");
    setDone("");
    try {
      await adminApi(`/matches/${m.match_id}/reveal`, { method: "POST" });
      setDone(`${names} 매칭을 보이게 했어요.`);
      await load();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      <PageTitle
        eyebrow="사용자"
        title="매칭 정지된 사용자"
        desc="매칭 정지된 사람은 서로 LIKE해도 매칭이 두 사람 모두에게 보이지 않아요. 본인은 정지 사실을 알 수 없어요. 하루(한국 시간 0시부터)에 매칭이 3번 생긴 사람은 자동으로 정지돼요. 숨겨진 매칭은 아래에서 하나씩 골라 다시 보이게 할 수 있어요."
      />
      {error && (
        <div className="mb-4">
          <Notice tone="error">{error}</Notice>
        </div>
      )}
      {done && (
        <div className="mb-4">
          <Notice tone="ok">{done}</Notice>
        </div>
      )}
      {!data ? (
        error ? null : <Spinner />
      ) : (
        <div className="space-y-10">
          <section>
            <p className="eyebrow mb-3">
              지금 매칭 정지 중 <span className="num">{data.users.length}</span>명
            </p>
            {data.users.length === 0 ? (
              <p className="text-[13.5px] text-ink-faint">매칭 정지된 사용자가 없어요. 정지는 사용자 상세 화면에서 할 수 있어요.</p>
            ) : (
              <ul className="divide-y divide-line rounded-card border border-line bg-paper-card text-[14px]">
                {data.users.map((u) => (
                  <li key={u.user_id} className="flex flex-wrap items-baseline justify-between gap-2 px-5 py-3">
                    <span>
                      <Link href={`/admin/users/${u.user_id}`} className="font-mono font-semibold underline underline-offset-4">
                        {u.subject_code}
                      </Link>
                      <span className="text-ink-soft"> · {u.nickname ?? "(탈퇴)"}</span>
                      {u.auto_suspended ? (
                        <span className="ml-2 rounded bg-brick-wash px-1.5 py-0.5 text-[11.5px] text-brick-deep">자동 · {u.suspend_reason ?? "하루 매칭 한도"}</span>
                      ) : (
                        u.suspend_reason && <span className="ml-2 text-[12.5px] text-ink-faint">사유: {u.suspend_reason}</span>
                      )}
                      {u.status !== "ACTIVE" && <span className="ml-2 text-[12.5px] text-brick">{USER_STATUS_LABEL[u.status] ?? u.status}</span>}
                    </span>
                    <span className="text-[13px] text-ink-faint">
                      {u.match_suspended_at ? `${dateTime(u.match_suspended_at)}부터` : "—"} · 숨겨진 매칭 <span className="num">{u.hidden_matches}</span>개
                    </span>
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-2 text-[12.5px] text-ink-faint">정지를 풀려면 이름을 눌러 사용자 상세 화면의 &lsquo;매칭 정지 풀기&rsquo;를 누르세요. 풀어도 숨겨진 매칭은 그대로예요.</p>
          </section>

          <section>
            <p className="eyebrow mb-3">
              숨겨진 매칭 <span className="num">{data.hidden_matches.length}</span>개
            </p>
            {data.hidden_matches.length === 0 ? (
              <p className="text-[13.5px] text-ink-faint">숨겨진 매칭이 없어요.</p>
            ) : (
              <ul className="divide-y divide-line rounded-card border border-line bg-paper-card text-[14px]">
                {data.hidden_matches.map((m) => (
                  <li key={m.match_id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3">
                    <span className="space-y-1">
                      <span className="flex flex-wrap items-baseline gap-x-2">
                        {m.members.map((p, i) => (
                          <span key={p.user_id}>
                            {i > 0 && <span className="mr-2 text-ink-faint">♥</span>}
                            <Link href={`/admin/users/${p.user_id}`} className="font-mono underline underline-offset-4">
                              {p.subject_code}
                            </Link>
                            <span className="text-ink-soft"> {p.nickname ?? "(탈퇴)"}</span>
                            {p.match_suspended && <span className="ml-1 rounded bg-brick-wash px-1.5 py-0.5 text-[11.5px] text-brick-deep">정지 중</span>}
                          </span>
                        ))}
                      </span>
                      <span className="block text-[12.5px] text-ink-faint">
                        {dateTime(m.hidden_at)} 숨김
                        {m.reveal_blocked_reason && <span className="text-brick"> · {m.reveal_blocked_reason}</span>}
                      </span>
                    </span>
                    <Button size="sm" loading={busy === m.match_id} disabled={!!m.reveal_blocked_reason || (busy !== null && busy !== m.match_id)} onClick={() => reveal(m)}>
                      다시 보이게
                    </Button>
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-2 text-[12.5px] text-ink-faint">
              다시 보이게 하면 두 사람에게 방금 매칭된 것처럼 보이고 &lsquo;새로운 매칭&rsquo; 알림이 가요. 아직 정지 중인 사람이 있어도 보이게 할 수 있어요.
            </p>
          </section>
        </div>
      )}
    </>
  );
}
