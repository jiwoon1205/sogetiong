"use client";

import { useEffect, useState } from "react";
import { AgeRangeSlider } from "@/components/AgeRangeSlider";
import { Button, Checkbox, Notice } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import type { CampusWithDepts } from "@/lib/catalog";
import { cn } from "@/lib/format";
import { GENDER_LABEL, type MyProfile, type Preferences } from "@/lib/types";
import { useKstNewDay } from "@/lib/useKstNewDay";

// 가로 바 양 끝 기본값 (서버가 age_floor / age_cap을 보내면 그 값을 쓴다)
const AGE_FLOOR = 19;
const AGE_CAP = 35;
// 처음 설정할 때 가로 바의 시작 위치: 왼쪽 끝(가입 가능한 최소 나이, 19세)부터 27세까지
// (예전 기본값 20~27세는 19세 신입생을 기본으로 빼버려서 2026-09-30에 바꿈)
const DEFAULT_MAX_AGE = 27;
const DEFAULT_RANGE: [number, number] = [AGE_FLOOR, DEFAULT_MAX_AGE];

const EMPTY: Preferences = {
  configured: false,
  preferred_gender: "ANY",
  min_age: AGE_FLOOR,
  max_age: DEFAULT_MAX_AGE,
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
  // 나이: 가로 바에서 고른 범위와 "상관없음"을 따로 기억한다 → 상관없음을 껐다 켜도 고른 범위가 남아 있다
  const [ageRange, setAgeRange] = useState<[number, number]>(DEFAULT_RANGE);
  const [ageAny, setAgeAny] = useState(false);
  const [floor, setFloor] = useState(AGE_FLOOR);
  const [cap, setCap] = useState(AGE_CAP);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    Promise.all([api<Preferences>("/me/preferences"), api<MyProfile>("/me/profile")])
      .then(([res, profile]) => {
        // 설정 전이어도 가입할 때 고른 원하는 성별은 온다
        setP((prev) => (res.configured ? res : { ...prev, preferred_gender: res.preferred_gender, gender_locked_message: res.gender_locked_message }));
        const f = res.age_floor ?? AGE_FLOOR;
        const c = res.age_cap ?? AGE_CAP;
        setFloor(f);
        setCap(c);
        if (!res.configured) {
          // 서버가 알려준 왼쪽 끝부터 시작 (가입 최소 나이 설정이 바뀌어도 맞게)
          setAgeRange([f, Math.min(c, Math.max(f, DEFAULT_MAX_AGE))]);
        }
        if (res.configured) {
          const any = res.age_any ?? (res.min_age == null && res.max_age == null);
          setAgeAny(any);
          // 저장된 범위를 가로 바에 표시. 바를 벗어나는 값은 가장 가까운 끝으로, 비어 있는 쪽은 끝으로.
          // (상관없음이면 바는 흐리게 기본 위치에 두고, 끄면 그 위치에서 시작)
          if (!any) {
            const fit = (v: number) => Math.min(c, Math.max(f, v));
            const lo = fit(res.min_age ?? f);
            const hi = fit(res.max_age ?? c);
            setAgeRange([Math.min(lo, hi), Math.max(lo, hi)]);
          }
        }
        const mode = res.configured ? res.campus_mode : "ALL";
        // 예전 방식("내 캠퍼스만")도 체크박스로 보여준다
        if (mode === "ALL") setCampusIds(campuses.map((c) => c.id));
        else if (mode === "MY") setCampusIds([profile.campus_id]);
        else setCampusIds(res.campus_ids);
      })
      .catch((e) => setError(errorMessage(e)));
  }, [campuses]);

  // 화면을 띄워 둔 채 날짜(한국 시간)가 바뀌면 → "오늘 남은 횟수"만 다시 받아온다 (고르던 조건은 그대로 둔다)
  useKstNewDay(() => {
    api<Preferences>("/me/preferences")
      .then((res) => setP((prev) => ({ ...prev, changes_left_today: res.changes_left_today })))
      .catch(() => {});
  });

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
    // 상관없음 → 둘 다 비움. 오른쪽 끝("35세 이상") → 최대 나이 비움 (위쪽 제한 없음)
    const [lo, hi] = ageRange;
    const min_age = ageAny ? null : lo;
    const max_age = ageAny || hi >= cap ? null : hi;
    setLoading(true);
    try {
      const res = await api<Preferences>("/me/preferences", {
        method: "PUT",
        body: {
          min_age,
          max_age,
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

      <div className="space-y-1.5">
        <div className="flex items-baseline justify-between gap-3">
          <p id="age-label" className="text-[13px] font-medium text-ink-soft">나이 <span className="font-normal text-ink-faint">(만 나이)</span></p>
          <p className={cn("num text-[19px] font-medium tracking-tight", ageAny ? "text-ink-faint" : "text-ink")} aria-live="polite">
            {ageAny ? "나이 상관없음" : ageRangeText(ageRange, cap)}
          </p>
        </div>
        <div role="group" aria-labelledby="age-label" className="rounded-md border border-line bg-paper-card px-4 pb-2 pt-1">
          <AgeRangeSlider
            floor={floor}
            cap={cap}
            value={ageRange}
            disabled={ageAny}
            onChange={(next) => {
              setSaved(false);
              setAgeRange(next);
            }}
          />
          <div className="mt-1 border-t border-line pt-1">
            <Checkbox
              checked={ageAny}
              onChange={(v) => {
                setSaved(false);
                setAgeAny(v);
              }}
            >
              나이 상관없음
            </Checkbox>
          </div>
        </div>
        <p className="text-[12.5px] leading-relaxed text-ink-faint">
          모든 나이는 만 나이예요. 양쪽 끝을 끌어서 범위를 정해요. 상관없음으로 해도, 상대가 정한 나이 범위에 내가 들어가야 서로 추천돼요.
        </p>
      </div>

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

/** "만 22세 ~ 27세", "만 35세 이상", "만 25세" 처럼 가로 바 위에 크게 보여줄 문구 (모두 만 나이) */
function ageRangeText([lo, hi]: [number, number], cap: number) {
  if (lo >= cap) return `만 ${cap}세 이상`;
  if (hi >= cap) return `만 ${lo}세 ~ ${cap}세 이상`;
  if (lo === hi) return `만 ${lo}세`;
  return `만 ${lo}세 ~ ${hi}세`;
}
