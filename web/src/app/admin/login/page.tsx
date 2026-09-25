"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { AuthFrame } from "@/components/AuthFrame";
import { Steps } from "@/components/Steps";
import { Button, Field, Input, Notice, PageTitle } from "@/components/ui";
import { errorMessage } from "@/lib/api";
import { adminApi } from "@/lib/admin";

export default function AdminLoginPage() {
  const router = useRouter();
  const [step, setStep] = useState<0 | 1>(0);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
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

  return (
    <AuthFrame sub="운영">
      <Steps labels={["비밀번호", "2단계 인증"]} current={step} className="mb-9" />
      {step === 0 ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            run(async () => {
              await adminApi("/auth/login", { method: "POST", body: { email, password } });
              setStep(1);
            });
          }}
          className="space-y-5"
        >
          <PageTitle title="운영자 로그인" desc="모든 열람 기록은 감사 로그에 남습니다." />
          <Field label="관리자 이메일" htmlFor="email">
            <Input id="email" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </Field>
          <Field label="비밀번호" htmlFor="password">
            <Input id="password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </Field>
          {error && <Notice tone="error">{error}</Notice>}
          <Button type="submit" size="lg" className="w-full" loading={loading}>
            다음
          </Button>
        </form>
      ) : (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            run(async () => {
              await adminApi("/auth/2fa", { method: "POST", body: { code } });
              router.replace("/admin");
            });
          }}
          className="space-y-5"
        >
          <PageTitle title="인증 앱 코드" desc="Google Authenticator 등 인증 앱에 표시된 6자리 숫자를 입력하세요." />
          <Field label="6자리 코드" htmlFor="otp">
            <Input
              id="otp"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
              className="num text-center text-[22px] tracking-[0.5em]"
              autoFocus
              required
            />
          </Field>
          {error && <Notice tone="error">{error}</Notice>}
          <Button type="submit" size="lg" className="w-full" loading={loading} disabled={code.length !== 6}>
            확인
          </Button>
        </form>
      )}
    </AuthFrame>
  );
}
