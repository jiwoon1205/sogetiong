"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { Fragment, useEffect, useState } from "react";
import { Button, Field, Input, Notice, Segmented, Spinner, Textarea } from "@/components/ui";
import { adminApi, useAdmin } from "@/lib/admin";
import { errorMessage } from "@/lib/api";
import { cn, dateTime } from "@/lib/format";
import { SCORE_LABELS, TIER_LABEL, TIER_OPTIONS, type AppearanceTier, type Scores } from "@/lib/types";

type Detail = {
  photo_id: string;
  subject_code: string;
  review_status: string;
  uploaded_at: string;
  reviewed_at: string | null;
  reject_reason: string | null;
  review_note: string | null; // 내부 메모 (운영진 전용)
  image_url: string;
  image_urls?: string[]; // 함께 제출한 사진 전부 (최대 3장, 첫 번째가 대표)
  photo_count?: number;
  evaluation_history: (Scores & { tier: AppearanceTier | null; note: string | null; created_at: string })[];
};

const PHOTO_STATUS: Record<string, string> = { PENDING: "대기", IN_REVIEW: "확인 중", APPROVED: "승인", REJECTED: "반려", SUPERSEDED: "대체됨" };

// 평가 기준표 (설계도 §5). 운영진끼리 기준을 맞추기 위한 초안 — 실제 운영 전에 다듬을 것.
const RUBRIC: { range: string; text: string }[] = [
  { range: "9–10", text: "매우 뛰어남. 누구에게나 강한 인상을 줌" },
  { range: "7–8", text: "좋음. 호감을 주는 수준" },
  { range: "5–6", text: "보통. 특별히 흠잡을 곳 없음" },
  { range: "3–4", text: "아쉬움. 개선 여지가 분명함" },
  { range: "1–2", text: "판단이 어렵거나 사진 상태가 좋지 않음" },
];

export default function PhotoReview() {
  const { photoId } = useParams<{ photoId: string }>();
  const router = useRouter();
  const admin = useAdmin();
  const [detail, setDetail] = useState<Detail | null>(null);
  const [decision, setDecision] = useState<"APPROVED" | "REJECTED">("APPROVED");
  const [scores, setScores] = useState<Partial<Scores>>({});
  // 외모 등급 (내부 전용). 추천 순서에만 쓰이고 사용자에게는 보이지 않는다
  const [tier, setTier] = useState<AppearanceTier | "">("");
  const [note, setNote] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    adminApi<Detail>(`/photo-reviews/${photoId}`)
      .then((d) => {
        setDetail(d);
        // 전에 쓴 내부 메모가 있으면 그대로 채워 둔다 (다시 평가할 때 지워지지 않게)
        if (d.review_note) setNote(d.review_note);
        const last = d.evaluation_history[0];
        if (last) {
          setScores({ overall_impression: last.overall_impression, style: last.style, grooming: last.grooming, photo_vibe: last.photo_vibe });
          if (last.tier) setTier(last.tier);
        }
      })
      .catch((e) => setError(errorMessage(e)));
  }, [photoId]);

  async function submit() {
    setError("");
    setLoading(true);
    try {
      await adminApi(`/photo-reviews/${photoId}/evaluation`, {
        method: "PUT",
        body:
          decision === "APPROVED"
            ? { decision, ...scores, tier, note: note || null }
            : { decision, reject_reason: reason, note: note || null },
      });
      router.push("/admin/photos");
    } catch (err) {
      setError(errorMessage(err));
      setLoading(false);
    }
  }

  if (!detail) return error ? <Notice tone="error">{error}</Notice> : <Spinner />;
  const complete = SCORE_LABELS.every((s) => scores[s.key]) && tier !== "";
  const canEvaluate = admin.can("photos:evaluate");

  return (
    <>
      <Link href="/admin/photos" className="text-[13px] text-ink-soft hover:text-ink">
        ← 대기열
      </Link>
      <div className="mb-8 mt-3 flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <h1 className="font-mono text-[26px] font-semibold tracking-wide">{detail.subject_code}</h1>
        <p className="text-[13px] text-ink-faint">{dateTime(detail.uploaded_at)} 제출 · 현재 상태 {PHOTO_STATUS[detail.review_status] ?? detail.review_status}</p>
      </div>

      <div className="grid gap-8 lg:grid-cols-[minmax(0,26rem)_1fr]">
        <div>
          {(detail.image_urls?.length ?? 1) > 1 && (
            <p className="mb-2 text-[13px] text-ink-soft">
              함께 제출한 사진 <span className="num">{detail.image_urls!.length}</span>장 · 모두 보고 한 번에 평가해요
            </p>
          )}
          <div className="space-y-3">
            {(detail.image_urls ?? [detail.image_url]).map((url, i, all) => (
              <div key={url} className="relative overflow-hidden rounded-card border border-line bg-paper-deep" onContextMenu={(e) => e.preventDefault()}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={url} alt={`검수 대상 사진 ${i + 1}`} draggable={false} className="w-full select-none" />
                {all.length > 1 && (
                  <span className="absolute left-2 top-2 rounded-sm bg-ink/75 px-1.5 py-0.5 text-[11px] text-paper">
                    <span className="num">{i + 1}</span>/<span className="num">{all.length}</span>
                  </span>
                )}
              </div>
            ))}
          </div>
          <p className="mt-3 text-[12px] leading-relaxed text-ink-faint">
            이 화면 열람은 기록됩니다. 사진에는 열람자 정보가 워터마크로 들어가 있어요. 저장·캡처하지 마세요.
          </p>
        </div>

        <div className="space-y-7">
          {(detail.review_status === "APPROVED" || detail.review_status === "REJECTED") && (
            <section className="rounded-card border border-line bg-paper-card px-5 py-4 text-[13.5px]">
              <p className="eyebrow mb-3">검수 결과</p>
              <dl className="grid grid-cols-[5.5rem_1fr] gap-x-3 gap-y-2">
                <dt className="text-ink-faint">결과</dt>
                <dd className={cn("font-semibold", detail.review_status === "REJECTED" && "text-brick")}>{PHOTO_STATUS[detail.review_status]}</dd>
                {detail.reviewed_at && (
                  <>
                    <dt className="text-ink-faint">검수 일시</dt>
                    <dd>{dateTime(detail.reviewed_at)}</dd>
                  </>
                )}
                {detail.review_status === "REJECTED" && (
                  <>
                    <dt className="text-ink-faint">반려 사유</dt>
                    <dd className="whitespace-pre-wrap">{detail.reject_reason || "—"}</dd>
                  </>
                )}
                <dt className="text-ink-faint">내부 메모</dt>
                <dd className="whitespace-pre-wrap">{detail.review_note || <span className="text-ink-faint">없음</span>}</dd>
              </dl>
            </section>
          )}

          {canEvaluate ? (
            <>
              <Segmented
                value={decision}
                onChange={setDecision}
                options={[
                  { value: "APPROVED", label: "승인하고 평가" },
                  { value: "REJECTED", label: "반려" },
                ]}
              />

              {decision === "APPROVED" ? (
                <div className="space-y-6">
                  {SCORE_LABELS.map((s) => (
                    <div key={s.key}>
                      <div className="mb-2 flex items-baseline justify-between">
                        <p className="text-[14.5px] font-semibold">{s.label}</p>
                        <p className="text-[12px] text-ink-faint">{s.hint}</p>
                      </div>
                      <div className="grid grid-cols-10 gap-1">
                        {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
                          <button
                            key={n}
                            type="button"
                            onClick={() => setScores((prev) => ({ ...prev, [s.key]: n }))}
                            className={cn(
                              "num h-10 rounded-[5px] border text-[14px] transition-colors",
                              scores[s.key] === n ? "border-ink bg-ink text-paper" : "border-line bg-paper-card text-ink-soft hover:border-line-strong",
                            )}
                          >
                            {n}
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                  <div>
                    <div className="mb-2 flex items-baseline justify-between">
                      <p className="text-[14.5px] font-semibold">외모 등급</p>
                      <p className="text-[12px] text-ink-faint">내부 전용 · 사용자에게 보이지 않음</p>
                    </div>
                    <Segmented<AppearanceTier | ""> value={tier} onChange={setTier} options={TIER_OPTIONS} />
                    <p className="mt-2 text-[12px] leading-relaxed text-ink-faint">
                      같은 등급끼리 추천에 먼저 나와요. 점수와 별개로 운영진이 직접 정하고, 본인을 포함해 누구에게도 공개되지 않아요.
                    </p>
                  </div>
                  <details className="rounded-md border border-line bg-paper-card px-4 py-3 text-[13px]">
                    <summary className="cursor-pointer font-medium text-ink-soft">평가 기준표</summary>
                    <dl className="mt-3 space-y-1.5">
                      {RUBRIC.map((r) => (
                        <div key={r.range} className="grid grid-cols-[3rem_1fr] gap-2">
                          <dt className="num font-semibold">{r.range}</dt>
                          <dd className="text-ink-soft">{r.text}</dd>
                        </div>
                      ))}
                    </dl>
                    <p className="mt-3 text-ink-faint">인종·종교·장애·건강 등 외모와 관계없는 특성은 평가에 반영하지 않습니다.</p>
                  </details>
                </div>
              ) : (
                <Field label="반려 사유 (사용자에게 전달돼요)" htmlFor="reason">
                  <Input id="reason" value={reason} maxLength={300} onChange={(e) => setReason(e.target.value)} placeholder="얼굴이 잘 보이지 않아요. 정면 사진으로 다시 올려주세요." />
                </Field>
              )}

              <Field label="내부 메모 (운영진만 볼 수 있어요)" htmlFor="note">
                <Textarea id="note" value={note} maxLength={500} onChange={(e) => setNote(e.target.value)} rows={2} />
              </Field>

              {error && <Notice tone="error">{error}</Notice>}
              <Button size="lg" className="w-full" loading={loading} disabled={decision === "APPROVED" ? !complete : !reason.trim()} onClick={submit}>
                {decision === "APPROVED" ? "평가 저장" : "반려하기"}
              </Button>
            </>
          ) : (
            <Notice>평가 권한이 없습니다.</Notice>
          )}

          {detail.evaluation_history.length > 0 && (
            <section>
              <p className="eyebrow mb-3">이 사용자의 평가 이력</p>
              <table className="w-full text-[13px]">
                <thead className="text-left text-ink-faint">
                  <tr>
                    <th className="pb-2 font-normal">일시</th>
                    {SCORE_LABELS.map((s) => (
                      <th key={s.key} className="pb-2 text-right font-normal">
                        {s.label.slice(0, 2)}
                      </th>
                    ))}
                    <th className="pb-2 text-right font-normal">등급</th>
                  </tr>
                </thead>
                <tbody className="num">
                  {detail.evaluation_history.map((h) => (
                    <Fragment key={h.created_at}>
                      <tr className="border-t border-line">
                        <td className="py-2 text-ink-soft">{dateTime(h.created_at)}</td>
                        {SCORE_LABELS.map((s) => (
                          <td key={s.key} className="py-2 text-right font-semibold">
                            {h[s.key]}
                          </td>
                        ))}
                        <td className="py-2 text-right font-semibold">{h.tier ? TIER_LABEL[h.tier] : "—"}</td>
                      </tr>
                      {h.note && (
                        <tr>
                          <td colSpan={SCORE_LABELS.length + 2} className="whitespace-pre-wrap pb-2 font-sans text-[12.5px] text-ink-soft">
                            메모: {h.note}
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </section>
          )}
        </div>
      </div>
    </>
  );
}
