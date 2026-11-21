"use client";

import { useRef, useState } from "react";
import { BoardAvatar } from "@/components/board/BoardAvatar";
import { Button, Field, Input, Notice } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import type { BoardMe, MyBoardProfile } from "@/lib/board";
import { cn } from "@/lib/format";

/**
 * 게시판 프로필 만들기·고치기 (2026-11-22).
 * - 닉네임: 게시판 전용 (소개팅 닉네임과 따로). 30일에 한 번 바꿀 수 있다.
 * - 프사: 기본 그림 또는 직접 올리기 (검수 없이 바로 모두에게 보임)
 * - 점수: 공개 안 함 또는 4개 중 하나
 */
export function ProfileEditor({ me, onSaved, onCancel }: { me: BoardMe; onSaved: (p: MyBoardProfile) => void; onCancel?: () => void }) {
  const existing = me.profile;
  const [nickname, setNickname] = useState(existing?.nickname ?? "");
  const [score, setScore] = useState<string | null>(existing?.shown_score ?? null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [removeAvatar, setRemoveAvatar] = useState(false);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const canChangeName = !existing || new Date(existing.next_nickname_change) <= new Date();
  const scores = me.my_scores ?? {};

  function pick(f: File | null) {
    setFile(f);
    setRemoveAvatar(false);
    setPreview(f ? URL.createObjectURL(f) : null);
  }

  async function save() {
    setSaving(true);
    setError("");
    try {
      let profile: MyBoardProfile;
      if (!existing) {
        profile = await api<MyBoardProfile>("/board/profile", { method: "POST", body: { nickname, shown_score: score } });
      } else {
        profile = await api<MyBoardProfile>("/board/profile", {
          method: "PATCH",
          body: { nickname: canChangeName ? nickname : null, shown_score: score, change_score: true },
        });
      }
      if (file) {
        const form = new FormData();
        form.append("file", file);
        profile = await api<MyBoardProfile>("/board/profile/avatar", { method: "POST", form });
      } else if (removeAvatar && existing?.has_avatar) {
        profile = await api<MyBoardProfile>("/board/profile/avatar", { method: "DELETE" });
      }
      onSaved(profile);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setSaving(false);
    }
  }

  const showAvatar = preview ? null : !removeAvatar && existing?.has_avatar ? existing : { id: null, has_avatar: false };

  return (
    <div className="space-y-6">
      <div>
        <p className="mb-2 text-[13px] font-medium text-ink-soft">프로필 사진 (선택)</p>
        <div className="flex items-center gap-4">
          {preview ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={preview} alt="" className="h-16 w-16 rounded-full border border-line object-cover" />
          ) : (
            <BoardAvatar author={showAvatar!} size={64} />
          )}
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" size="sm" type="button" onClick={() => fileRef.current?.click()}>
              사진 고르기
            </Button>
            {(preview || (existing?.has_avatar && !removeAvatar)) && (
              <Button
                variant="ghost"
                size="sm"
                type="button"
                onClick={() => {
                  pick(null);
                  setRemoveAvatar(true);
                }}
              >
                기본 그림으로
              </Button>
            )}
          </div>
          <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={(e) => pick(e.target.files?.[0] ?? null)} />
        </div>
        <p className="mt-2 text-[12.5px] text-brick">이 사진은 게시판에서 모두에게 보여요. 검수 없이 바로 올라가고, 부적절하면 신고로 지워져요.</p>
      </div>

      <Field label="게시판 닉네임" hint={canChangeName ? `${me.config.nickname_min}~${me.config.nickname_max}자 · 소개팅 닉네임과 따로예요 · 30일에 한 번 바꿀 수 있어요` : `닉네임은 ${new Date(existing!.next_nickname_change).toLocaleDateString("ko-KR", { month: "long", day: "numeric" })}부터 바꿀 수 있어요`}>
        <Input value={nickname} maxLength={me.config.nickname_max} disabled={!canChangeName} onChange={(e) => setNickname(e.target.value)} placeholder="예: 봄바람" />
      </Field>

      <div>
        <p className="mb-2 text-[13px] font-medium text-ink-soft">내 점수 공개 (선택)</p>
        <div className="grid grid-cols-2 gap-2">
          <ScoreButton active={score === null} onClick={() => setScore(null)} label="공개 안 함" />
          {Object.entries(me.score_labels).map(([key, label]) => (
            <ScoreButton key={key} active={score === key} onClick={() => setScore(key)} label={label} value={scores[key]} />
          ))}
        </div>
        <p className="mt-2 text-[12.5px] text-ink-faint">고른 점수 하나만 닉네임 옆에 보여요. 나머지 점수와 소개팅 프로필은 게시판에서 절대 보이지 않아요.</p>
      </div>

      <div className="rounded-md border border-line bg-paper-deep px-4 py-3 text-[12.5px] leading-relaxed text-ink-soft">
        게시판에서 다른 사람에게 보이는 것: 프사 · 닉네임 · 성별 · 학교(캠퍼스) · (고르면) 점수 1개
      </div>

      {error && <Notice tone="error">{error}</Notice>}
      <div className="flex gap-2">
        {onCancel && (
          <Button variant="secondary" className="flex-1" onClick={onCancel}>
            취소
          </Button>
        )}
        <Button className="flex-1" loading={saving} disabled={nickname.trim().length < me.config.nickname_min} onClick={save}>
          {existing ? "저장" : "게시판 프로필 만들기"}
        </Button>
      </div>
    </div>
  );
}

function ScoreButton({ active, onClick, label, value }: { active: boolean; onClick: () => void; label: string; value?: number }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex items-center justify-between rounded-md border px-3 py-2.5 text-[14px]",
        active ? "border-ink bg-ink text-paper" : "border-line bg-paper-card hover:border-line-strong",
      )}
    >
      <span>{label}</span>
      {value !== undefined && <span className="num font-semibold">{value}</span>}
    </button>
  );
}
