"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Checkbox } from "@/components/ui";
import { cn, shortSchoolName } from "@/lib/format";

/** 학교별 캠퍼스 (매칭 조건 /me/preferences/campuses) */
export type SchoolCampuses = { id: string; name: string; mine: boolean; campuses: { id: string; name: string }[] };

/**
 * 만날 학교·캠퍼스 고르기 (2026-11-22).
 * - [모든 학교 추천] 버튼: 누르면 모든 학교·캠퍼스 (앞으로 새로 열리는 학교도 자동 포함)
 * - 그 아래 학과 고르기처럼 생긴 칸을 누르면 목록이 펼쳐지고, 스크롤하면서 여러 개를 체크한다
 *   (학교 이름을 누르면 그 학교 캠퍼스 전부, 검색칸으로 학교 찾기)
 * - 기본은 모두 선택
 */
export function SchoolPicker({
  schools,
  value,
  onChange,
}: {
  schools: SchoolCampuses[];
  value: string[];
  onChange: (ids: string[]) => void;
}) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const boxRef = useRef<HTMLDivElement>(null);

  const allIds = useMemo(() => schools.flatMap((s) => s.campuses.map((c) => c.id)), [schools]);
  const all = allIds.length > 0 && allIds.every((id) => value.includes(id));
  const chosen = new Set(value);

  // 바깥을 누르면 목록 닫기
  useEffect(() => {
    if (!open) return;
    function onDown(e: PointerEvent) {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("pointerdown", onDown);
    return () => document.removeEventListener("pointerdown", onDown);
  }, [open]);

  // 버튼에 보일 요약: 전체 / "고려대 서울 외 3곳"
  const summary = useMemo(() => {
    if (all) return `모든 학교 (${allIds.length}개 캠퍼스)`;
    const names: string[] = [];
    for (const s of schools) {
      const picked = s.campuses.filter((c) => chosen.has(c.id));
      if (picked.length === 0) continue;
      if (picked.length === s.campuses.length) names.push(shortSchoolName(s.name));
      else for (const c of picked) names.push(`${shortSchoolName(s.name)} ${c.name.replace(/캠퍼스$/, "")}`);
    }
    if (names.length === 0) return "학교를 골라 주세요";
    return names.length <= 2 ? names.join(", ") : `${names.slice(0, 2).join(", ")} 외 ${names.length - 2}곳`;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, schools, all]);

  const shown = q.trim()
    ? schools.filter((s) => s.name.includes(q.trim()) || shortSchoolName(s.name).includes(q.trim()) || s.campuses.some((c) => c.name.includes(q.trim())))
    : schools;

  function toggleCampus(id: string) {
    onChange(chosen.has(id) ? value.filter((x) => x !== id) : [...value, id]);
  }

  function toggleSchool(s: SchoolCampuses) {
    const ids = s.campuses.map((c) => c.id);
    const every = ids.every((id) => chosen.has(id));
    onChange(every ? value.filter((x) => !ids.includes(x)) : [...new Set([...value, ...ids])]);
  }

  function toggleAll() {
    if (all) {
      // 모든 학교 → 우리 학교만 남기고 목록을 펼쳐서 고르게 한다
      const mine = schools.filter((s) => s.mine).flatMap((s) => s.campuses.map((c) => c.id));
      onChange(mine);
      setOpen(true);
    } else {
      onChange(allIds);
      setOpen(false);
    }
  }

  return (
    <div ref={boxRef} className="space-y-2">
      <button
        type="button"
        onClick={toggleAll}
        aria-pressed={all}
        className={cn(
          "flex h-11 w-full items-center justify-center gap-2 rounded-md border text-[14.5px] font-medium transition-colors",
          all ? "border-ink bg-ink text-paper" : "border-line bg-paper-card text-ink hover:border-line-strong",
        )}
      >
        {all && (
          <svg viewBox="0 0 12 10" className="h-3 w-3" aria-hidden>
            <path d="M1 5l3.2 3L11 1.5" fill="none" stroke="currentColor" strokeWidth="1.8" />
          </svg>
        )}
        모든 학교 추천
      </button>

      <div className="relative">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          className="field flex w-full items-center justify-between gap-2 text-left"
        >
          <span className={cn("truncate", value.length === 0 && "text-ink-faint")}>{summary}</span>
          <svg viewBox="0 0 12 8" className={cn("h-2 w-3 shrink-0 transition-transform", open && "rotate-180")} aria-hidden>
            <path d="M1 1.5l5 5 5-5" fill="none" stroke="currentColor" strokeWidth="1.4" />
          </svg>
        </button>

        {open && (
          <div className="mt-1.5 rounded-md border border-line-strong bg-paper-card shadow-lg">
            <div className="border-b border-line p-2">
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="학교 이름으로 찾기"
                aria-label="학교 찾기"
                className="field h-9 text-[15px]"
              />
            </div>
            <div className="max-h-72 overflow-y-auto overscroll-contain px-3 py-1">
              {shown.length === 0 && <p className="py-6 text-center text-[13px] text-ink-faint">찾는 학교가 없어요.</p>}
              {shown.map((s) => {
                const ids = s.campuses.map((c) => c.id);
                const every = ids.every((id) => chosen.has(id));
                return (
                  <div key={s.id} className="border-b border-line py-1 last:border-b-0">
                    <Checkbox checked={every} onChange={() => toggleSchool(s)}>
                      <span className="font-semibold">{s.name}</span>
                      {s.mine && <span className="text-ink-faint"> · 우리 학교</span>}
                    </Checkbox>
                    {s.campuses.length > 1 && (
                      <div className="flex flex-wrap gap-x-5 pl-7">
                        {s.campuses.map((c) => (
                          <Checkbox key={c.id} checked={chosen.has(c.id)} onChange={() => toggleCampus(c.id)}>
                            {c.name.replace(/캠퍼스$/, "")}
                          </Checkbox>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
            <div className="flex items-center justify-between border-t border-line px-3 py-2">
              <span className="text-[12.5px] text-ink-faint">{value.length}개 캠퍼스 선택</span>
              <button type="button" onClick={() => setOpen(false)} className="rounded-md bg-ink px-4 py-1.5 text-[13.5px] font-medium text-paper">
                완료
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
