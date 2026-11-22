"use client";

import { useCallback, useEffect, useState } from "react";
import { Button, Notice, PageTitle, Spinner } from "@/components/ui";
import { adminApi } from "@/lib/admin";
import { errorMessage } from "@/lib/api";
import { cn, dateTime } from "@/lib/format";

type Votes = { AGREE: number; DISAGREE: number };
type Comment = {
  id: string;
  vote: "AGREE" | "DISAGREE";
  gender: "MALE" | "FEMALE" | null;
  goal: string | null;
  comment: string;
  created_at: string;
};
type Data = {
  open: boolean;
  total: number;
  votes: Votes;
  by_gender: { MALE: Votes; FEMALE: Votes };
  by_goal: { SERIOUS: Votes; FRIEND: Votes; CASUAL: Votes; NONE: Votes };
  comments: Comment[];
};

const GENDER_LABEL: Record<string, string> = { MALE: "남", FEMALE: "여" };
const GOAL_LABEL: Record<string, string> = { SERIOUS: "진지한 연애", FRIEND: "대학교 친구", CASUAL: "캐주얼한 만남", NONE: "안 고름" };

/**
 * 설문 (2026-11-22 찬반 투표: 찾는 관계 '대학교 친구' 없애기)
 * - 처음부터 켜져 있어서 아직 답하지 않은 모든 사용자에게 로그인·가입 직후 뜬다
 * - 끄면 바로 아무에게도 안 뜬다. 응답은 그대로 남는다
 * - 닉네임·이메일 없이 성별·지금 찾는 관계만 보여준다
 */
export default function SurveyAdminPage() {
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(
    () =>
      adminApi<Data>("/survey")
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

  async function toggle() {
    if (!data) return;
    const next = !data.open;
    const msg = next
      ? "투표를 다시 시작할까요?\n\n아직 답하지 않은 모든 사용자에게 다음 접속 때 투표가 먼저 떠요."
      : "투표를 끝낼까요?\n\n바로 아무에게도 뜨지 않아요. 지금까지의 응답은 그대로 남아요.";
    if (!window.confirm(msg)) return;
    setBusy(true);
    try {
      await adminApi("/survey/open", { method: "PUT", body: { open: next } });
      await load();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  if (!data) return error ? <Notice tone="error">{error}</Notice> : <Spinner />;

  return (
    <div className="space-y-10">
      <PageTitle title="설문 · 찬반 투표" desc="찾는 관계에서 '대학교 친구'를 없앨까요? 계정당 한 번, 찬성/반대 + 하고 싶은 말(선택)." />

      <section className="flex flex-wrap items-center justify-between gap-4 rounded-card border border-line bg-paper-card px-5 py-4">
        <div>
          <p className="text-[15px] font-semibold text-ink">
            {data.open ? "투표 받는 중" : "투표 꺼짐"}
            <span className={cn("ml-2 inline-block h-2 w-2 rounded-full align-middle", data.open ? "bg-moss" : "bg-line-strong")} />
          </p>
          <p className="mt-1 text-[13px] text-ink-soft">
            응답 <b className="num text-ink">{data.total}</b>명
          </p>
        </div>
        <Button variant={data.open ? "danger" : "primary"} onClick={toggle} loading={busy}>
          {data.open ? "투표 끝내기" : "투표 다시 시작"}
        </Button>
      </section>

      {error && <Notice tone="error">{error}</Notice>}

      <section className="space-y-4">
        <VoteBar label="전체" votes={data.votes} big />
        <div className="grid gap-4 sm:grid-cols-2">
          <VoteBar label="남성" votes={data.by_gender.MALE} />
          <VoteBar label="여성" votes={data.by_gender.FEMALE} />
        </div>
        <p className="eyebrow pt-2">지금 고른 찾는 관계별</p>
        <div className="grid gap-4 sm:grid-cols-2">
          {(["FRIEND", "SERIOUS", "CASUAL", "NONE"] as const).map((k) => (
            <VoteBar key={k} label={GOAL_LABEL[k]} votes={data.by_goal[k]} />
          ))}
        </div>
      </section>

      <section>
        <p className="eyebrow mb-3">하고 싶은 말 {data.comments.length}</p>
        {data.comments.length === 0 ? (
          <p className="text-[14px] text-ink-faint">아직 적은 말이 없어요.</p>
        ) : (
          <ul className="divide-y divide-line rounded-card border border-line bg-paper-card">
            {data.comments.map((c) => (
              <li key={c.id} className="space-y-1.5 px-5 py-4 text-[14px]">
                <p className="text-[12.5px] text-ink-faint">
                  <span className={c.vote === "AGREE" ? "font-semibold text-ink" : "font-semibold text-brick"}>{c.vote === "AGREE" ? "찬성" : "반대"}</span> ·{" "}
                  {c.gender ? GENDER_LABEL[c.gender] : "성별 없음"} · {GOAL_LABEL[c.goal ?? "NONE"]} · {dateTime(c.created_at)}
                </p>
                <p className="whitespace-pre-wrap leading-relaxed text-ink">{c.comment}</p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function VoteBar({ label, votes, big }: { label: string; votes: Votes; big?: boolean }) {
  const total = votes.AGREE + votes.DISAGREE;
  const agree = total ? Math.round((votes.AGREE / total) * 100) : 0;
  return (
    <div className="rounded-card border border-line bg-paper-card px-5 py-4">
      <div className="mb-2 flex items-baseline justify-between">
        <p className={cn("font-semibold text-ink", big ? "text-[16px]" : "text-[14px]")}>{label}</p>
        <p className="num text-[12.5px] text-ink-faint">{total}명</p>
      </div>
      <div className="flex h-3 overflow-hidden rounded-full bg-paper-deep">
        {total > 0 && <div className="bg-ink" style={{ width: `${agree}%` }} />}
        {total > 0 && <div className="bg-brick" style={{ width: `${100 - agree}%` }} />}
      </div>
      <div className="mt-2 flex justify-between text-[13px]">
        <span className="text-ink">
          찬성 <b className="num">{votes.AGREE}</b> {total > 0 && <span className="text-ink-faint">({agree}%)</span>}
        </span>
        <span className="text-brick">
          반대 <b className="num">{votes.DISAGREE}</b> {total > 0 && <span className="text-ink-faint">({100 - agree}%)</span>}
        </span>
      </div>
    </div>
  );
}
