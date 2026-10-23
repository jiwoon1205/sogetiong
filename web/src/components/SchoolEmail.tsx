"use client";

import { useEffect, useState } from "react";
import { EmailInput, Field, Segmented } from "@/components/ui";
import { api } from "@/lib/api";
import { shortSchoolName } from "@/lib/format";

export type University = { id: string; name: string; email_domain: string };

const LAST_SCHOOL_KEY = "hufting:last-school";

/** 가입할 수 있는 (열린) 학교 목록. 한국외대가 먼저 온다 (2026-10-24 경희대 확장). */
export function useUniversities() {
  const [universities, setUniversities] = useState<University[]>([]);
  useEffect(() => {
    api<{ universities: University[] }>("/universities")
      .then((r) => setUniversities(r.universities))
      .catch(() => {});
  }, []);
  return universities;
}

/** 학교 고르기 + 학교 메일 입력 (가입·로그인·비밀번호 재설정).
 *  열린 학교가 하나면 지금처럼 메일 칸만 보인다. 둘 이상이면 위에 학교 버튼이 생기고,
 *  고른 학교의 메일 뒷부분(@khu.ac.kr 등)이 고정 글자로 붙는다. 마지막에 고른 학교를 기억한다. */
export function SchoolEmailField({
  id = "email",
  value,
  onChange,
  required,
}: {
  id?: string;
  value: string;
  onChange: (email: string) => void;
  required?: boolean;
}) {
  const universities = useUniversities();
  // 마지막에 고른 학교 (이 브라우저에만 기억). 목록에 없으면(닫힌 학교 등) 첫 학교
  const [domain, setDomain] = useState(() => {
    try {
      return typeof window === "undefined" ? "" : (window.localStorage.getItem(LAST_SCHOOL_KEY) ?? "");
    } catch {
      return "";
    }
  });
  const current =
    universities.find((u) => u.email_domain === domain)?.email_domain ?? universities[0]?.email_domain ?? "hufs.ac.kr";

  function pick(next: string) {
    // 앞부분은 그대로 두고 뒷부분만 바꾼다
    const local = value.toLowerCase().endsWith(`@${current}`) ? value.slice(0, -(current.length + 1)) : "";
    setDomain(next);
    onChange(local ? `${local}@${next}` : value.includes("@") ? value : "");
    try {
      window.localStorage.setItem(LAST_SCHOOL_KEY, next);
    } catch {}
  }

  return (
    <>
      {universities.length > 1 && (
        <Field label="학교">
          <Segmented<string>
            value={current}
            onChange={pick}
            options={universities.map((u) => ({ value: u.email_domain, label: shortSchoolName(u.name) }))}
          />
        </Field>
      )}
      <Field label="학교 이메일" htmlFor={id}>
        <EmailInput id={id} value={value} onChange={onChange} domain={current} required={required} />
      </Field>
    </>
  );
}
