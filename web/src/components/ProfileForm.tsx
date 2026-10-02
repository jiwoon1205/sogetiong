"use client";

import { useEffect, useState } from "react";
import { Button, Field, Input, Notice, Segmented, Select, Tag, Textarea } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { mailto, useSupportEmail, type CampusWithDepts } from "@/lib/catalog";
import { FACE_TYPES, HEIGHT_MAX_CM, HEIGHT_MIN_CM, type MyProfile } from "@/lib/types";

type Visibility = "" | "show" | "hide";
const VISIBILITY_OPTIONS: { value: Visibility; label: string }[] = [
  { value: "show", label: "공개" },
  { value: "hide", label: "비공개" },
];
const toVisibility = (v: boolean | null | undefined): Visibility => (v == null ? "" : v ? "show" : "hide");

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
  // 캠퍼스·학과 공개 여부: 처음에는 비워 두고 사용자가 직접 고르게 한다 (정해진 기본값 없음)
  const [showCampus, setShowCampus] = useState<Visibility>("");
  const [showDept, setShowDept] = useState<Visibility>("");
  const supportEmail = useSupportEmail();
  // 키 입력칸 글자 그대로 (지우는 중인 빈칸도 받아야 해서 숫자와 따로 둔다)
  const [heightText, setHeightText] = useState("");

  useEffect(() => {
    api<MyProfile>("/me/profile")
      .then((res) => {
        setP(res);
        setHeightText(res.height_cm ? String(res.height_cm) : "");
        setShowCampus(toVisibility(res.show_campus));
        // 학과를 아직 안 골랐으면 학과 공개 여부도 새로 고르게 한다
        setShowDept(res.department_locked ? toVisibility(res.show_department) : "");
      })
      .catch((e) => setError(errorMessage(e)));
  }, []);

  if (!p) return error ? <Notice tone="error">{error}</Notice> : null;
  const myCampus = campuses.find((c) => c.id === p.campus_id);
  const campusName = myCampus?.name ?? p.campus_name ?? "";

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
    if (!p.department_id) return setError("학과를 선택해주세요. 학과는 매칭에만 쓰이고, 다른 학생에게 보여줄지는 직접 고를 수 있어요.");
    if (!showCampus || !showDept) return setError("캠퍼스와 학과를 다른 학생에게 보여줄지 골라주세요.");
    // 키: 비워 두면 안 적은 것. 적었다면 140~210 사이 정수만
    const heightTrim = heightText.trim();
    const height = heightTrim === "" ? null : Number(heightTrim);
    if (height !== null && (!Number.isInteger(height) || height < HEIGHT_MIN_CM || height > HEIGHT_MAX_CM)) {
      return setError(`키는 ${HEIGHT_MIN_CM}~${HEIGHT_MAX_CM} 사이 숫자로 적어주세요. 적고 싶지 않으면 비워 두세요.`);
    }
    setLoading(true);
    try {
      const updated = await api<MyProfile>("/me/profile", {
        method: "PATCH",
        body: {
          nickname: p.nickname,
          // 학과는 처음 한 번만 보낸다 (이후에는 바꿀 수 없음)
          department_id: p.department_locked ? undefined : p.department_id,
          show_campus: showCampus === "show",
          show_department: showDept === "show",
          mbti: p.mbti || null,
          bio: p.bio ?? "",
          ideal_type: p.ideal_type ?? "",
          face_type: p.face_type ?? null,
          height_cm: height,
          interests: p.interests,
        },
      });
      setP(updated);
      setHeightText(updated.height_cm ? String(updated.height_cm) : "");
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
        {p.department_locked ? (
          <Field label={`학과${campusName ? ` (${campusName})` : ""}`}>
            <Input value={p.department_name ?? ""} readOnly aria-readonly className="bg-paper-deep/60 text-ink-soft" />
          </Field>
        ) : (
          <Field label={`학과${campusName ? ` (${campusName})` : ""} · 필수`} htmlFor="dept">
            <Select id="dept" value={p.department_id ?? ""} onChange={(e) => set("department_id", e.target.value || null)}>
              <option value="" disabled>
                학과를 선택하세요
              </option>
              {myCampus?.departments.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </Select>
          </Field>
        )}
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
      {!p.department_locked && (
        // 학과 선택에서 그만두는 사람이 많아서 "왜 필수인지"를 먼저 알려준다 (2026-10-02)
        <div className="-mt-3 rounded-md bg-paper-deep/60 px-3 py-2.5 text-[12.5px] leading-relaxed text-ink-soft">
          <p className="font-medium">학과는 왜 필수인가요?</p>
          <p className="mt-1">
            학과는 <b>매칭 알고리즘</b>을 위한 정보예요. &quot;같은 과 사람은 안 만나기&quot;를 켠 사람끼리 서로 추천되지 않도록
            확인하는 데 쓰여요.
          </p>
          <p className="mt-1">
            <b>공개 여부는 직접 정할 수 있어요.</b> 아래에서 비공개를 고르면 다른 학생에게는 학과가 보이지 않아요.
          </p>
        </div>
      )}
      {supportEmail &&
        (p.department_locked ? (
          <p className="-mt-3 text-[12.5px] leading-relaxed text-ink-faint">
            학과는 바꿀 수 없어요. 잘못 선택했다면{" "}
            <a
              className="underline underline-offset-4"
              href={mailto(
                supportEmail,
                "[학과 변경 요청]",
                `현재 학과: ${p.department_name ?? ""}\n바꿀 학과: \n\n※ 가입한 학교 메일로 보내주셔야 본인 확인이 돼요.`,
              )}
            >
              운영진에게 메일
            </a>
            로 알려주세요.
          </p>
        ) : (
          <p className="-mt-3 text-[12.5px] leading-relaxed text-ink-faint">
            학과는 저장한 뒤에는 바꿀 수 없으니 정확히 골라주세요.{" "}
            <a
              className="underline underline-offset-4"
              href={mailto(
                supportEmail,
                "[학과 추가 요청] 내 학과가 목록에 없어요",
                `캠퍼스: ${campusName}\n학과 이름: \n\n※ 가입한 학교 메일로 보내주세요. 확인 후 목록에 추가해 드릴게요.`,
              )}
            >
              내 학과가 목록에 없어요
            </a>
          </p>
        ))}

      <div className="grid gap-4 rounded-md border border-line bg-paper-card px-4 py-4 sm:grid-cols-2">
        <Field label="캠퍼스 공개">
          <Segmented value={showCampus} onChange={(v) => { setSaved(false); setShowCampus(v); }} options={VISIBILITY_OPTIONS} />
        </Field>
        <Field label="학과 공개">
          <Segmented value={showDept} onChange={(v) => { setSaved(false); setShowDept(v); }} options={VISIBILITY_OPTIONS} />
        </Field>
        <p className="text-[12.5px] leading-relaxed text-ink-faint sm:col-span-2">
          비공개로 해도 매칭 조건(캠퍼스, 같은 과 제외)에는 그대로 쓰여요. 공개 여부는 나중에 바꿀 수 있어요.
        </p>
      </div>

      <div className="space-y-2">
        <p className="text-[13px] font-medium text-ink-soft">
          얼굴상 <span className="text-ink-faint">· 선택, 1개</span>
        </p>
        <div className="flex flex-wrap gap-2">
          {FACE_TYPES.map((name) => (
            // 같은 걸 한 번 더 누르면 선택 취소
            <Tag key={name} active={p.face_type === name} onClick={() => set("face_type", p.face_type === name ? null : name)}>
              {name}
            </Tag>
          ))}
        </div>
      </div>

      <Field label="키 · 선택" htmlFor="height">
        <div className="flex items-center gap-2">
          <Input
            id="height"
            inputMode="numeric"
            pattern="[0-9]*"
            maxLength={3}
            className="w-28"
            value={heightText}
            onChange={(e) => {
              setSaved(false);
              setHeightText(e.target.value.replace(/[^0-9]/g, ""));
            }}
            placeholder="예) 172"
          />
          <span className="text-[14px] text-ink-soft">cm</span>
        </div>
      </Field>
      <p className="-mt-3 text-[12.5px] leading-relaxed text-ink-faint">
        얼굴상과 키는 다른 학생에게 &quot;본인이 입력한 정보&quot;로 보여요. 적지 않아도 추천에는 영향이 없어요.
      </p>

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
