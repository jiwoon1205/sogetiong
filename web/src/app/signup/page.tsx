"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AuthFrame } from "@/components/AuthFrame";
import { Steps } from "@/components/Steps";
import { Button, Checkbox, Field, Input, Notice, PageTitle, Segmented, Select } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";

type University = { id: string; name: string; email_domain: string };
type Campus = { id: string; name: string };
type Gender = "MALE" | "FEMALE";
type WantGender = Gender | "ANY";

export default function SignupPage() {
  const router = useRouter();
  const [step, setStep] = useState<0 | 1 | 2>(0);
  const [university, setUniversity] = useState<University | null>(null);
  const [campuses, setCampuses] = useState<Campus[]>([]);

  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [ticket, setTicket] = useState("");
  // 성별·원하는 성별은 가입 후 본인이 바꿀 수 없어서, 미리 골라두지 않고 직접 고르게 한다
  const [info, setInfo] = useState({
    nickname: "",
    gender: "" as Gender | "",
    want: "" as WantGender | "",
    birth: "",
    campus: "",
    pw: "",
    pw2: "",
  });
  const [agree, setAgree] = useState({ terms: false, privacy: false, appearance: false });

  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api<{ universities: University[] }>("/universities")
      .then(async ({ universities }) => {
        const uni = universities[0] ?? null;
        setUniversity(uni);
        if (uni) {
          const res = await api<{ campuses: Campus[] }>(`/universities/${uni.id}/campuses`);
          setCampuses(res.campuses);
        }
      })
      .catch((e) => setError(errorMessage(e)));
  }, []);

  async function run(fn: () => Promise<void>) {
    setError("");
    setLoading(true);
    try {
      await fn();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  const sendCode = (e: React.FormEvent) => {
    e.preventDefault();
    run(async () => {
      await api("/auth/email/send-code", { method: "POST", body: { email } });
      setNotice(`${email} 로 메일을 보냈어요. 인증번호는 10분 안에 입력해주세요. 이미 가입된 주소라면 인증번호 대신 로그인 안내 메일이 가요.`);
      setStep(1);
    });
  };

  const verify = (e: React.FormEvent) => {
    e.preventDefault();
    run(async () => {
      const res = await api<{ verification_ticket: string }>("/auth/email/verify", { method: "POST", body: { email, code } });
      setTicket(res.verification_ticket);
      setNotice("");
      setStep(2);
    });
  };

  const register = (e: React.FormEvent) => {
    e.preventDefault();
    if (!info.gender) return setError("성별을 골라주세요.");
    if (!info.want) return setError("만나고 싶은 상대의 성별을 골라주세요.");
    if (info.pw !== info.pw2) return setError("비밀번호가 서로 다릅니다.");
    if (!agree.terms || !agree.privacy || !agree.appearance) return setError("필수 항목에 모두 동의해주세요.");
    run(async () => {
      await api("/auth/register", {
        method: "POST",
        body: {
          verification_ticket: ticket,
          password: info.pw,
          nickname: info.nickname,
          gender: info.gender,
          preferred_gender: info.want,
          birth_date: info.birth,
          campus_id: info.campus,
          agree_terms: agree.terms,
          agree_privacy: agree.privacy,
          agree_appearance_public: agree.appearance,
        },
      });
      router.replace("/onboarding");
    });
  };

  const allAgreed = agree.terms && agree.privacy && agree.appearance;

  return (
    <AuthFrame
      footer={
        <>
          이미 가입했나요?{" "}
          <Link href="/login" className="font-medium text-ink underline underline-offset-4">
            로그인
          </Link>
        </>
      }
    >
      <Steps labels={["학교 메일", "인증번호", "기본 정보"]} current={step} className="mb-9" />

      {step === 0 && (
        <form onSubmit={sendCode} className="space-y-5">
          <PageTitle title="학교 메일로 확인할게요" desc={<>재학생 확인에만 쓰이고, 다른 학생에게는 절대 보이지 않아요.</>} />
          <Field label="학교 이메일" htmlFor="email" hint={university ? `@${university.email_domain} 주소만 사용할 수 있어요.` : undefined}>
            <Input id="email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder={`학번@${university?.email_domain ?? "hufs.ac.kr"}`} required />
          </Field>
          {error && <Notice tone="error">{error}</Notice>}
          <Button type="submit" size="lg" className="w-full" loading={loading}>
            인증번호 받기
          </Button>
        </form>
      )}

      {step === 1 && (
        <form onSubmit={verify} className="space-y-5">
          <PageTitle title="인증번호를 입력하세요" />
          {notice && <Notice>{notice}</Notice>}
          <Field label="6자리 숫자" htmlFor="code">
            <Input
              id="code"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
              className="num text-center text-[22px] tracking-[0.5em]"
              required
            />
          </Field>
          {error && <Notice tone="error">{error}</Notice>}
          <Button type="submit" size="lg" className="w-full" loading={loading} disabled={code.length !== 6}>
            확인
          </Button>
          <button type="button" onClick={() => { setStep(0); setCode(""); setError(""); }} className="w-full text-center text-[13.5px] text-ink-soft underline underline-offset-4">
            메일 주소 다시 입력하기
          </button>
        </form>
      )}

      {step === 2 && (
        <form onSubmit={register} className="space-y-5">
          <PageTitle
            title="기본 정보"
            desc="성별·만나고 싶은 상대·생년월일·캠퍼스는 가입 후 바꿀 수 없어요. 생년월일은 만 나이 계산에만 쓰여요."
          />
          <Field label="닉네임" htmlFor="nickname" hint="2~20자. 실명이나 학번이 드러나지 않게 지어주세요.">
            <Input id="nickname" value={info.nickname} maxLength={20} onChange={(e) => setInfo({ ...info, nickname: e.target.value })} required />
          </Field>
          <Field label="성별">
            <Segmented<Gender | "">
              value={info.gender}
              onChange={(g) => setInfo({ ...info, gender: g })}
              options={[
                { value: "FEMALE", label: "여성" },
                { value: "MALE", label: "남성" },
              ]}
            />
          </Field>
          <Field label="만나고 싶은 상대" hint="다른 학생에게는 보이지 않아요. 가입 후에는 바꿀 수 없으니 신중히 골라주세요.">
            <Segmented<WantGender | "">
              value={info.want}
              onChange={(w) => setInfo({ ...info, want: w })}
              options={[
                { value: "MALE", label: "남성" },
                { value: "FEMALE", label: "여성" },
                { value: "ANY", label: "상관없음" },
              ]}
            />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="생년월일" htmlFor="birth">
              <Input id="birth" type="date" value={info.birth} onChange={(e) => setInfo({ ...info, birth: e.target.value })} required />
            </Field>
            <Field label="캠퍼스" htmlFor="campus">
              <Select id="campus" value={info.campus} onChange={(e) => setInfo({ ...info, campus: e.target.value })} required>
                <option value="" disabled>
                  선택
                </option>
                {campuses.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
          <Field label="비밀번호" htmlFor="pw" hint="8자 이상, 영문과 숫자를 섞어주세요.">
            <Input id="pw" type="password" autoComplete="new-password" value={info.pw} onChange={(e) => setInfo({ ...info, pw: e.target.value })} required />
          </Field>
          <Field label="비밀번호 확인" htmlFor="pw2">
            <Input id="pw2" type="password" autoComplete="new-password" value={info.pw2} onChange={(e) => setInfo({ ...info, pw2: e.target.value })} required />
          </Field>

          <div className="rounded-md border border-line bg-paper-card px-4 py-3">
            <Checkbox checked={allAgreed} onChange={(v) => setAgree({ terms: v, privacy: v, appearance: v })}>
              <span className="font-semibold">전체 동의</span>
            </Checkbox>
            <div className="rule my-2" />
            <Checkbox checked={agree.terms} onChange={(v) => setAgree({ ...agree, terms: v })}>
              (필수) 이용약관
            </Checkbox>
            <Checkbox checked={agree.privacy} onChange={(v) => setAgree({ ...agree, privacy: v })}>
              (필수) 개인정보 수집·이용
            </Checkbox>
            <Checkbox checked={agree.appearance} onChange={(v) => setAgree({ ...agree, appearance: v })}>
              (필수) 제출한 사진을 운영진이 확인하고, 네 가지 항목의 외적 평가 점수가 다른 학생에게 공개되는 것에 동의합니다
            </Checkbox>
            <p className="mt-2 text-[12.5px] leading-relaxed text-ink-faint">
              사진 원본은 다른 학생에게 보이지 않습니다. 대화 내용은 안전 관리를 위해 운영진이 볼 수 있어요.{" "}
              <a href="/privacy" target="_blank" rel="noopener noreferrer" className="underline underline-offset-4">
                개인정보처리방침 보기
              </a>
            </p>
          </div>

          {error && <Notice tone="error">{error}</Notice>}
          <Button type="submit" size="lg" className="w-full" loading={loading}>
            가입하기
          </Button>
        </form>
      )}
    </AuthFrame>
  );
}
