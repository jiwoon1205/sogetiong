"use client";

import { useUniversities } from "@/components/SchoolEmail";
import { shortSchoolName } from "@/lib/format";

/** 첫 화면 맨 위 "○○ 재학생 전용" (2026-10-24 경희대 확장).
 *  열린 학교 이름을 서버에서 받아 보여준다. 받기 전·못 받으면 지금처럼 한국외대만.
 *  2026-11-21: 학교가 3개를 넘으면 전체 이름은 너무 길어서 짧은 이름으로 ("한국외대 · 경희대 · 고려대 …") */
export function SchoolsEyebrow() {
  const universities = useUniversities();
  // 2026-11-21: 학교가 7개 이상이면 이름 대신 "○개 대학"
  const names = !universities.length
    ? "한국외국어대학교"
    : universities.length <= 3
      ? universities.map((u) => u.name).join(" · ")
      : universities.length <= 6
        ? universities.map((u) => shortSchoolName(u.name)).join(" · ")
        : `${universities.length}개 대학`;
  return <p className="eyebrow mb-6 leading-relaxed">{names} 재학생 전용</p>;
}
