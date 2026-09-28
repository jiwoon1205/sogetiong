"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export type CampusWithDepts = { id: string; name: string; departments: { id: string; name: string }[] };

/** 문의 메일 주소 (학과 변경 요청, "내 학과가 목록에 없어요") */
export function useSupportEmail() {
  const [email, setEmail] = useState<string | null>(null);
  useEffect(() => {
    api<{ email: string }>("/support")
      .then((r) => setEmail(r.email))
      .catch(() => {});
  }, []);
  return email;
}

/** 메일 앱을 열어 제목·본문을 미리 채운다 */
export function mailto(email: string, subject: string, body: string) {
  return `mailto:${email}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
}

/** 학교의 캠퍼스·학과·관심사 목록을 한 번에 불러온다 */
export function useCatalog(universityId: string | undefined) {
  const [campuses, setCampuses] = useState<CampusWithDepts[]>([]);
  const [interests, setInterests] = useState<string[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!universityId) return;
    let alive = true;
    (async () => {
      const [{ campuses }, { interests }] = await Promise.all([
        api<{ campuses: { id: string; name: string }[] }>(`/universities/${universityId}/campuses`),
        api<{ interests: string[] }>("/interests"),
      ]);
      const withDepts = await Promise.all(
        campuses.map(async (c) => ({
          ...c,
          departments: (await api<{ departments: { id: string; name: string }[] }>(`/campuses/${c.id}/departments`)).departments,
        })),
      );
      if (alive) {
        setCampuses(withDepts);
        setInterests(interests);
        setLoaded(true);
      }
    })().catch(() => setLoaded(true));
    return () => {
      alive = false;
    };
  }, [universityId]);

  return { campuses, interests, loaded };
}
