"use client";

import { useUniversities } from "@/components/SchoolEmail";

/** 첫 화면 맨 위 "○○ 재학생 전용" (2026-10-24 경희대 확장).
 *  열린 학교 이름을 서버에서 받아 보여준다. 받기 전·못 받으면 지금처럼 한국외대만. */
export function SchoolsEyebrow() {
  const universities = useUniversities();
  const names = universities.length ? universities.map((u) => u.name).join(" · ") : "한국외국어대학교";
  return <p className="eyebrow mb-6">{names} 재학생 전용</p>;
}
