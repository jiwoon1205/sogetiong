"use client";

import { useEffect, useState } from "react";
import { Button, Checkbox, Field, Input, Notice } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import type { CampusWithDepts } from "@/lib/catalog";
import { GENDER_LABEL, type MyProfile, type Preferences } from "@/lib/types";

const EMPTY: Preferences = {
  configured: false,
  preferred_gender: "ANY",
  min_age: 20,
  max_age: 27,
  campus_mode: "ALL",
  campus_ids: [],
  exclude_same_department: false,
};

/** 매칭 조건. 이 내용은 본인만 볼 수 있다.
 *  원하는 성별은 가입할 때 정해서 여기서는 보여주기만 한다 (바꾸려면 운영진에게 메일). */
export function PreferencesForm({
  campuses,
  submitLabel = "저장",
  onSaved,
}: {
  campuses: CampusWithDepts[];
  submitLabel?: string;
  onSaved?: () => void;
}) {
  const [p, setP] = useState<Preferences>(EMPTY);
  // 만날 캠퍼스: 체크한 캠퍼스 목록 (전부 체크 = 모든 캠퍼스)
  const [campusIds, setCampusIds] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    Promise.all([api<Preferences>("/me/preferences"), api<MyProfile>("/me/profile")])
      .then(([res, profile]) => {
        // 설정 전이어도 가입할 때 고른 원하는 성별은 온다
        setP((prev) => (res.configured ? res : { ...prev, preferred_gender: res.preferred_gender, gender_locked_message: res.gender_locked_message }));
        const mode = res.configured ? res.campus_mode : "ALL";
        // 예전 방식("내 캠퍼스만")도 체크박스로 보여준다
        if (mode === "ALL") setCampusIds(campuses.map((c) => c.id));
        else if (mode === "MY") setCampusIds([profile.campus_id]);
        else setCampusIds(res.campus_ids);
      })
      .catch((e) => setError(errorMessage(e)));
  }, [campuses]);

  function change(next: Partial<Preferences>) {
    setSaved(false);
    setP((prev) => ({ ...prev, ...next }));
  }

  function toggleCampus(id: string) {
    setSaved(false);
    setCampusIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (campusIds.length === 0) return setError("만날 캠퍼스를 하나 이상 골라주세요.");
    const all = campuses.every((c) => campusIds.includes(c.id));
    setLoading(true);
    try {
      const res = await api<Preferences>("/me/preferences", {
        method: "PUT",
        body: {
          min_age: p.min_age,
          max_age: p.max_age,
          campus_mode: all ? "ALL" : "SELECTED",
          campus_ids: all ? [] : campusIds,
          exclude_same_department: p.exclude_same_department,
        },
      });
      setP(res);
      setSaved(true);
      onSaved?.();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  const perDay = p.changes_per_day ?? 3;

  return (
    <form onSubmit={save} className="space-y-7">
      <Notice>
        여기서 정한 조건은 상대에게 보이지 않아요. 조건에 맞지 않는 사람은 이유를 알리지 않고 조용히 걸러집니다.
        {p.configured && (
          <>
            {" "}
            조건은 하루에 {perDay}번까지 바꿀 수 있어요 (오늘 남은 횟수 <span className="num">{p.changes_left_today ?? perDay}</span>번).
          </>
        )}
      </Notice>

      <div className="space-y-1.5">
        <p className="text-[13px] font-medium text-ink-soft">만나고 싶은 상대</p>
        <div className="rounded-md border border-line bg-paper-card px-4 py-3 text-[14.5px]">{GENDER_LABEL[p.preferred_gender]}</div>
        <p className="text-[12.5px] leading-relaxed text-ink-faint">
          {p.gender_locked_message ?? "가입할 때 고른 값이에요. 바꾸려면 운영진에게 메일로 요청해주세요."}
        </p>
      </div>

      <Field label="나이">
        <div className="flex items-center gap-3">
          <Input type="number" min={19} max={60} value={p.min_age} onChange={(e) => change({ min_age: Number(e.target.value) })} className="num text-center" aria-label="최소 나이" />
          <span className="text-ink-faint">~</span>
          <Input type="number" min={19} max={60} value={p.max_age} onChange={(e) => change({ max_age: Number(e.target.value) })} className="num text-center" aria-label="최대 나이" />
          <span className="shrink-0 text-[14px] text-ink-soft">세</span>
        </div>
      </Field>

      <div className="space-y-1.5">
        <p className="text-[13px] font-medium text-ink-soft">만날 캠퍼스</p>
        <div className="flex flex-wrap gap-x-6 rounded-md border border-line bg-paper-card px-4 py-2">
          {campuses.map((c) => (
            <Checkbox key={c.id} checked={campusIds.includes(c.id)} onChange={() => toggleCampus(c.id)}>
              {c.name.replace(/캠퍼스$/, "")}
            </Checkbox>
          ))}
        </div>
      </div>

      <div className="space-y-1.5">
        <p className="text-[13px] font-medium text-ink-soft">학과</p>
        <div className="rounded-md border border-line bg-paper-card px-4 py-2">
          <Checkbox checked={p.exclude_same_department} onChange={(v) => change({ exclude_same_department: v })}>
            같은 과 학생은 추천하지 않기
          </Checkbox>
        </div>
        <p className="text-[12.5px] leading-relaxed text-ink-faint">
          둘 중 한 명이라도 켜면 같은 과끼리는 서로 추천되지 않아요. 이미 매칭된 상대에게는 적용되지 않아요.
        </p>
      </div>

      <p className="text-[12.5px] leading-relaxed text-ink-faint">
        캠퍼스·학과를 비공개로 해도, 조건을 바꿔 가며 추천 결과를 보면 짐작될 수 있어요. 그래서 조건 변경 횟수를 제한해요.
      </p>

      {error && <Notice tone="error">{error}</Notice>}
      {saved && !onSaved && <Notice tone="ok">저장했어요.</Notice>}
      <Button type="submit" size="lg" className="w-full" loading={loading}>
        {submitLabel}
      </Button>
    </form>
  );
}
