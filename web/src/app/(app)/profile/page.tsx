"use client";

import { useCallback, useEffect, useState } from "react";
import { PhotoUpload } from "@/components/PhotoUpload";
import { ProfileCard } from "@/components/ProfileCard";
import { ProfileForm } from "@/components/ProfileForm";
import { Button, Notice, PageTitle, ScoreRow, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { useCatalog } from "@/lib/catalog";
import { dateTime } from "@/lib/format";
import { useSession } from "@/lib/session";
import { SCORE_LABELS, type MyProfile, type Scores } from "@/lib/types";

type Photo = {
  photo_id: string;
  photo_count?: number;
  review_status: string;
  reject_reason: string | null;
  uploaded_at: string;
  reviewed_at: string | null;
};
// 새 사진을 지금 낼 수 있는지 (서버가 알려줌). 평가 후 wait_days(7일) 안에는 "바로 재검토"를 계정당 1번만 쓸 수 있다
type Resubmit = {
  allowed: boolean;
  uses_free_rereview: boolean;
  free_rereview_left: boolean;
  next_available_at: string | null;
  wait_days?: number;
};

const PHOTO_STATUS: Record<string, string> = {
  PENDING: "검수 대기 중",
  IN_REVIEW: "AI가 평가하는 중",
  APPROVED: "승인됨",
  REJECTED: "반려됨",
  SUPERSEDED: "새 사진으로 대체됨",
};

export default function ProfilePage() {
  const { me, refresh } = useSession();
  const { campuses, interests, loaded } = useCatalog(me.university_id);
  const [profile, setProfile] = useState<MyProfile | null>(null);
  const [evaluation, setEvaluation] = useState<{ evaluated: boolean; scores?: Scores; evaluated_at?: string } | null>(null);
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [resubmit, setResubmit] = useState<Resubmit | null>(null);
  const [tab, setTab] = useState<"preview" | "edit">("preview");
  const [uploading, setUploading] = useState(false);

  const load = useCallback(async () => {
    const [p, e, ph] = await Promise.all([
      api<MyProfile>("/me/profile"),
      api<{ evaluated: boolean; scores?: Scores; evaluated_at?: string }>("/me/evaluation"),
      api<{ photos: Photo[]; resubmit?: Resubmit }>("/me/photos"),
    ]);
    setProfile(p);
    // 학과를 아직 고르지 않았으면 바로 수정 화면을 연다
    if (!p.department_locked) setTab("edit");
    setEvaluation(e);
    setPhotos(ph.photos);
    setResubmit(ph.resubmit ?? null);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (!profile || !evaluation || !loaded) return <Spinner />;
  const latest = photos[0];

  return (
    <div className="mx-auto max-w-app">
      <PageTitle eyebrow="내 프로필" title={profile.nickname} desc="다른 학생에게는 아래 카드 모습 그대로 보여요." />

      <div className="mb-6 flex gap-6 border-b border-line text-[14px]">
        {(["preview", "edit"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)} className={tab === t ? "-mb-px border-b-2 border-ink pb-3 font-semibold" : "pb-3 text-ink-faint hover:text-ink"}>
            {t === "preview" ? "미리보기" : "수정하기"}
          </button>
        ))}
      </div>

      {tab === "preview" ? (
        <ProfileCard card={profile} />
      ) : (
        <ProfileForm
          campuses={campuses}
          interests={interests}
          onSaved={(p) => {
            setProfile(p);
          }}
        />
      )}

      <section className="mt-12">
        <p className="eyebrow mb-4">외적 평가</p>
        <div className="rounded-card border border-line bg-paper-card p-6">
          {evaluation.evaluated && evaluation.scores ? (
            <div className="space-y-2.5">
              {SCORE_LABELS.map((s) => (
                <ScoreRow key={s.key} label={s.label} value={evaluation.scores![s.key]} />
              ))}
              <p className="pt-3 text-[12.5px] text-ink-faint">{dateTime(evaluation.evaluated_at!)} 평가 · AI가 매긴 참고 정보예요.</p>
            </div>
          ) : (
            <p className="text-[14px] text-ink-soft">아직 평가가 없어요. 사진 검수가 끝나면 표시돼요.</p>
          )}

          <div className="rule my-5" />
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-[13px] text-ink-faint">제출한 사진</p>
              <p className="mt-0.5 text-[14.5px] font-medium">
                {latest ? PHOTO_STATUS[latest.review_status] ?? latest.review_status : "제출하지 않음"}
                {latest && (latest.photo_count ?? 1) > 1 && <span className="font-normal text-ink-faint"> · <span className="num">{latest.photo_count}</span>장</span>}
              </p>
              {latest?.review_status === "REJECTED" && latest.reject_reason && <p className="mt-1 text-[13px] text-brick">사유: {latest.reject_reason}</p>}
            </div>
            {!uploading && (resubmit?.allowed ?? true) && (
              <Button variant="secondary" size="sm" onClick={() => setUploading(true)}>
                {latest ? (resubmit?.uses_free_rereview ? "바로 재검토 요청" : "새 사진 제출") : "사진 제출"}
              </Button>
            )}
          </div>
          {resubmit && !resubmit.allowed && resubmit.next_available_at && (
            <p className="mt-3 text-[12.5px] leading-relaxed text-ink-faint">
              바로 재검토는 이미 사용했어요. {dateTime(resubmit.next_available_at)}부터 새 사진을 제출할 수 있어요.
            </p>
          )}
          {uploading && (
            <div className="mt-6">
              {resubmit?.uses_free_rereview ? (
                <Notice>
                  평가 후 {resubmit.wait_days ?? 7}일 안에 바로 재검토를 요청할 수 있는 기회는 <b>계정당 한 번</b>이에요. 새 사진이 승인되면 기회를 쓴 것으로 처리돼요 (반려되면 다시 쓸 수 있어요).
                </Notice>
              ) : (
                <Notice>한 번에 최대 3장까지 제출할 수 있어요. 검수 전인 이전 사진은 새 사진으로 바뀌어요.</Notice>
              )}
              <div className="mt-5">
                <PhotoUpload
                  onUploaded={async () => {
                    setUploading(false);
                    await Promise.all([load(), refresh()]);
                  }}
                />
              </div>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
