"use client";

import { useEffect, useState } from "react";
import { Button, Checkbox, Field, Input, Notice, Select, Tag, Textarea } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import type { CampusWithDepts } from "@/lib/catalog";
import type { MyProfile } from "@/lib/types";

const MBTI = ["", "INTJ", "INTP", "ENTJ", "ENTP", "INFJ", "INFP", "ENFJ", "ENFP", "ISTJ", "ISFJ", "ESTJ", "ESFJ", "ISTP", "ISFP", "ESTP", "ESFP"];

export function ProfileForm({
  campuses,
  interests,
  submitLabel = "저장",
  onSaved,
}: {
  campuses: CampusWithDepts[];
  interests: string[];
  submitLabel?: string;
  onSaved?: (p: MyProfile) => void;
}) {
  const [p, setP] = useState<MyProfile | null>(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api<MyProfile>("/me/profile").then(setP).catch((e) => setError(errorMessage(e)));
  }, []);

  if (!p) return error ? <Notice tone="error">{error}</Notice> : null;
  const myCampus = campuses.find((c) => c.id === p.campus_id);

  function set<K extends keyof MyProfile>(key: K, value: MyProfile[K]) {
    setSaved(false);
    setP((prev) => (prev ? { ...prev, [key]: value } : prev));
  }

  function toggleInterest(name: string) {
    if (!p) return;
    const has = p.interests.includes(name);
    if (!has && p.interests.length >= 10) return setError("관심사는 최대 10개까지 고를 수 있어요.");
    setError("");
    set("interests", has ? p.interests.filter((x) => x !== name) : [...p.interests, name]);
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!p) return;
    setError("");
    setLoading(true);
    try {
      const updated = await api<MyProfile>("/me/profile", {
        method: "PATCH",
        body: {
          nickname: p.nickname,
          department_id: p.department_id || undefined,
          clear_department: !p.department_id,
          show_department: p.show_department,
          mbti: p.mbti || null,
          bio: p.bio ?? "",
          ideal_type: p.ideal_type ?? "",
          interests: p.interests,
        },
      });
      setP(updated);
      setSaved(true);
      onSaved?.(updated);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={save} className="space-y-6">
      <Field label="닉네임" htmlFor="nickname">
        <Input id="nickname" value={p.nickname} maxLength={20} onChange={(e) => set("nickname", e.target.value)} />
      </Field>

      <div className="grid grid-cols-[1fr_7.5rem] gap-3">
        <Field label={`학과${myCampus ? ` (${myCampus.name})` : ""}`} htmlFor="dept">
          <Select id="dept" value={p.department_id ?? ""} onChange={(e) => set("department_id", e.target.value || null)}>
            <option value="">선택 안 함</option>
            {myCampus?.departments.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="MBTI" htmlFor="mbti">
          <Select id="mbti" value={p.mbti ?? ""} onChange={(e) => set("mbti", e.target.value || null)}>
            {MBTI.map((m) => (
              <option key={m} value={m}>
                {m || "선택 안 함"}
              </option>
            ))}
          </Select>
        </Field>
      </div>
      {p.department_id && (
        <Checkbox checked={p.show_department} onChange={(v) => set("show_department", v)}>
          다른 학생에게 학과 공개하기
        </Checkbox>
      )}

      <Field label="자기소개" htmlFor="bio" hint={`${(p.bio ?? "").length}/500`}>
        <Textarea id="bio" maxLength={500} value={p.bio ?? ""} onChange={(e) => set("bio", e.target.value)} placeholder="어떤 하루를 보내는지, 요즘 빠져 있는 것, 대화하고 싶은 주제…" rows={4} />
      </Field>

      <Field label="이상형" htmlFor="ideal" hint={`${(p.ideal_type ?? "").length}/300`}>
        <Textarea id="ideal" maxLength={300} value={p.ideal_type ?? ""} onChange={(e) => set("ideal_type", e.target.value)} placeholder="외모보다 대화가 잘 통하는 사람이면 좋겠어요." rows={3} />
      </Field>

      <div className="space-y-2">
        <p className="text-[13px] font-medium text-ink-soft">
          관심사 <span className="num text-ink-faint">{p.interests.length}/10</span>
        </p>
        <div className="flex flex-wrap gap-2">
          {interests.map((name) => (
            <Tag key={name} active={p.interests.includes(name)} onClick={() => toggleInterest(name)}>
              {name}
            </Tag>
          ))}
        </div>
      </div>

      {error && <Notice tone="error">{error}</Notice>}
      {saved && !onSaved && <Notice tone="ok">저장했어요.</Notice>}
      <Button type="submit" size="lg" className="w-full" loading={loading}>
        {submitLabel}
      </Button>
    </form>
  );
}
