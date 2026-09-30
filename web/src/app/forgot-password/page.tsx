"use client";

import Link from "next/link";
import { useState } from "react";
import { AuthFrame } from "@/components/AuthFrame";
import { Steps } from "@/components/Steps";
import { Button, ButtonLink, EmailInput, Field, Input, Notice, PageTitle } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";

/**
 * 비밀번호 재설정
 * 0) 학교 이메일 입력 → 재설정 인증번호 발송
 * 1) 인증번호 + 새 비밀번호 입력 → 변경 (모든 기기에서 로그아웃됨)
 * 2) 완료 → 로그인 화면으로
 */
export default function ForgotPasswordPage() {
  const [step, setStep] = useState<0 | 1 | 2>(0);
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");

  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);

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

  const requestCode = (e: React.FormEvent) => {
    e.preventDefault();
    run(async () => {
      const res = await api<{ message: string }>("/auth/password/reset-request", { method: "POST", body: { email } });
      setNotice(res.message);
      setCode("");
      setStep(1);
    });
  };

  const reset = (e: React.FormEvent) => {
    e.preventDefault();
    if (pw !== pw2) return setError("새 비밀번호가 서로 다릅니다.");
    run(async () => {
      await api("/auth/password/reset", { method: "POST", body: { email, code, new_password: pw } });
      setStep(2);
    });
  };

  return (
    <AuthFrame
      footer={
        <>
          비밀번호가 기억났나요?{" "}
          <Link href="/login" className="font-medium text-ink underline underline-offset-4">
            로그인
          </Link>
        </>
      }
    >
      <Steps labels={["학교 메일", "새 비밀번호", "완료"]} current={step} className="mb-9" />

      {step === 0 && (
        <form onSubmit={requestCode} className="space-y-5">
          <PageTitle title="비밀번호 재설정" desc="가입할 때 쓴 학교 이메일로 인증번호를 보내드릴게요." />
          <Field label="학교 이메일" htmlFor="email">
            <EmailInput id="email" value={email} onChange={setEmail} required />
          </Field>
          {error && <Notice tone="error">{error}</Notice>}
          <Button type="submit" size="lg" className="w-full" loading={loading}>
            인증번호 받기
          </Button>
        </form>
      )}

      {step === 1 && (
        <form onSubmit={reset} className="space-y-5">
          <PageTitle title="새 비밀번호 정하기" desc="메일로 받은 6자리 숫자는 10분 동안 유효해요." />
          {notice && <Notice>{notice}</Notice>}
          <Field label="인증번호 6자리" htmlFor="code">
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
          <Field label="새 비밀번호" htmlFor="pw" hint="8자 이상, 영문과 숫자를 섞어주세요.">
            <Input id="pw" type="password" autoComplete="new-password" value={pw} onChange={(e) => setPw(e.target.value)} required />
          </Field>
          <Field label="새 비밀번호 확인" htmlFor="pw2">
            <Input id="pw2" type="password" autoComplete="new-password" value={pw2} onChange={(e) => setPw2(e.target.value)} required />
          </Field>
          {error && <Notice tone="error">{error}</Notice>}
          <Button type="submit" size="lg" className="w-full" loading={loading} disabled={code.length !== 6}>
            비밀번호 바꾸기
          </Button>
          <button
            type="button"
            onClick={() => {
              setStep(0);
              setError("");
              setNotice("");
            }}
            className="w-full text-center text-[13.5px] text-ink-soft underline underline-offset-4"
          >
            메일이 안 왔나요? 다시 받기
          </button>
        </form>
      )}

      {step === 2 && (
        <div className="space-y-6">
          <PageTitle title="비밀번호를 바꿨어요" desc="보안을 위해 모든 기기에서 로그아웃되었어요. 새 비밀번호로 다시 로그인해주세요." />
          <ButtonLink href="/login" size="lg" className="w-full">
            로그인하러 가기
          </ButtonLink>
        </div>
      )}
    </AuthFrame>
  );
}
