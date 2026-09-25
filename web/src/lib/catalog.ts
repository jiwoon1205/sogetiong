"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export type CampusWithDepts = { id: string; name: string; departments: { id: string; name: string }[] };

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
