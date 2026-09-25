"use client";

import { useEffect, useMemo, useState } from "react";
import { Button, Field, Input, Notice, Segmented, Tag } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import type { CampusWithDepts } from "@/lib/catalog";
import type { Preferences } from "@/lib/types";

const EMPTY: Preferences = {
  configured: false,
  preferred_gender: "ANY",
  min_age: 20,
  max_age: 27,
  campus_mode: "ALL",
  campus_ids: [],
  excluded_department_ids: [],
  preferred_department_ids: [],
};

/** 매칭 조건. 이 내용은 본인만 볼 수 있다. */
export function PreferencesForm({
  campuses,
  defaultGender,
  submitLabel = "저장",
  onSaved,
}: {
  campuses: CampusWithDepts[];
  defaultGender?: "MALE" | "FEMALE" | "ANY";
  submitLabel?: string;
  onSaved?: () => void;
}) {
  const [p, setP] = useState<Preferences>({ ...EMPTY, preferred_gender: defaultGender ?? "ANY" });
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(false);
  const [deptMode, setDeptMode] = useState<"exclude" | "prefer">("exclude");

  useEffect(() => {
    api<Preferences>("/me/preferences").then((res) => {
      if (res.configured) setP(res);
    });
  }, []);

  const allDepts = useMemo(
    () => campuses.flatMap((c) => c.departments.map((d) => ({ ...d, campus: c.name }))),
    [campuses],
  );

  function toggle(list: "campus_ids" | "excluded_department_ids" | "preferred_department_ids", id: string) {
    setSaved(false);
    setP((prev) => {
      const has = prev[list].includes(id);
      const next = { ...prev, [list]: has ? prev[list].filter((x) => x !== id) : [...prev[list], id] };
      // 같은 학과를 제외와 선호에 동시에 둘 수 없다
      if (!has && list === "excluded_department_ids") next.preferred_department_ids = prev.preferred_department_ids.filter((x) => x !== id);
      if (!has && list === "preferred_department_ids") next.excluded_department_ids = prev.excluded_department_ids.filter((x) => x !== id);
      return next;
    });
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { configured: _c, ...body } = p;
      await api("/me/preferences", { method: "PUT", body });
      setSaved(true);
      onSaved?.();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={save} className="space-y-7">
      <Notice>여기서 정한 조건은 상대에게 보이지 않아요. 조건에 맞지 않는 사람은 이유를 알리지 않고 조용히 걸러집니다.</Notice>

      <Field label="만나고 싶은 상대">
        <Segmented
          value={p.preferred_gender}
          onChange={(v) => { setSaved(false); setP({ ...p, preferred_gender: v }); }}
          options={[
            { value: "MALE", label: "남성" },
            { value: "FEMALE", label: "여성" },
            { value: "ANY", label: "상관없음" },
          ]}
        />
      </Field>

      <Field label="나이">
        <div className="flex items-center gap-3">
          <Input type="number" min={19} max={60} value={p.min_age} onChange={(e) => { setSaved(false); setP({ ...p, min_age: Number(e.target.value) }); }} className="num text-center" aria-label="최소 나이" />
          <span className="text-ink-faint">~</span>
          <Input type="number" min={19} max={60} value={p.max_age} onChange={(e) => { setSaved(false); setP({ ...p, max_age: Number(e.target.value) }); }} className="num text-center" aria-label="최대 나이" />
          <span className="shrink-0 text-[14px] text-ink-soft">세</span>
        </div>
      </Field>

      <Field label="캠퍼스">
        <Segmented
          value={p.campus_mode}
          onChange={(v) => { setSaved(false); setP({ ...p, campus_mode: v }); }}
          options={[
            { value: "MY", label: "내 캠퍼스만" },
            { value: "ALL", label: "모든 캠퍼스" },
            { value: "SELECTED", label: "직접 선택" },
          ]}
        />
        {p.campus_mode === "SELECTED" && (
          <div className="flex flex-wrap gap-2 pt-2">
            {campuses.map((c) => (
              <Tag key={c.id} active={p.campus_ids.includes(c.id)} onClick={() => toggle("campus_ids", c.id)}>
                {c.name}
              </Tag>
            ))}
          </div>
        )}
      </Field>

      <div className="space-y-3">
        <div className="flex items-end justify-between">
          <p className="text-[13px] font-medium text-ink-soft">학과</p>
          <div className="flex gap-4 text-[13px]">
            <button type="button" onClick={() => setDeptMode("exclude")} className={deptMode === "exclude" ? "font-semibold text-ink underline underline-offset-4" : "text-ink-faint"}>
              제외할 학과 {p.excluded_department_ids.length > 0 && <span className="num">{p.excluded_department_ids.length}</span>}
            </button>
            <button type="button" onClick={() => setDeptMode("prefer")} className={deptMode === "prefer" ? "font-semibold text-ink underline underline-offset-4" : "text-ink-faint"}>
              선호 학과 {p.preferred_department_ids.length > 0 && <span className="num">{p.preferred_department_ids.length}</span>}
            </button>
          </div>
        </div>
        <p className="text-[12.5px] text-ink-faint">
          {deptMode === "exclude" ? "선택한 학과 학생은 추천되지 않아요." : "선택한 학과 학생이 조금 더 앞에 추천돼요."}
        </p>
        {campuses.map((c) => (
          <div key={c.id}>
            <p className="mb-2 mt-3 text-[12px] text-ink-faint">{c.name}</p>
            <div className="flex flex-wrap gap-2">
              {c.departments.map((d) => {
                const list = deptMode === "exclude" ? "excluded_department_ids" : "preferred_department_ids";
                return (
                  <Tag key={d.id} tone={deptMode === "exclude" ? "brick" : "ink"} active={p[list].includes(d.id)} onClick={() => toggle(list, d.id)}>
                    {d.name}
                  </Tag>
                );
              })}
            </div>
          </div>
        ))}
        {allDepts.length === 0 && <p className="text-[13px] text-ink-faint">학과 목록이 없습니다.</p>}
      </div>

      {error && <Notice tone="error">{error}</Notice>}
      {saved && !onSaved && <Notice tone="ok">저장했어요.</Notice>}
      <Button type="submit" size="lg" className="w-full" loading={loading}>
        {submitLabel}
      </Button>
    </form>
  );
}
