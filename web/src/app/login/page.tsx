"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { AuthFrame } from "@/components/AuthFrame";
import { Button, EmailInput, Field, Input, Notice, PageTitle } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { firstStep } from "@/lib/onboarding";
import type { Me } from "@/lib/types";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await api("/auth/login", { method: "POST", body: { email, password } });
      // 가입 과정(프로필·조건·사진)이 덜 끝났으면 멈춘 곳부터 이어서 하게 한다
      const me = await api<Me>("/me").catch(() => null);
      router.replace(me && firstStep(me.onboarding) !== -1 ? "/onboarding" : "/discover");
    } catch (err) {
      setError(errorMessage(err));
      setLoading(false);
    }
  }

  return (
    <AuthFrame
      footer={
        <>
          처음이신가요?{" "}
          <Link href="/signup" className="font-medium text-ink underline underline-offset-4">
            학교 메일로 가입하기
          </Link>
        </>
      }
    >
      <PageTitle title="다시 오셨네요" desc="학교 이메일과 비밀번호로 로그인하세요." />
      <form onSubmit={submit} className="space-y-5">
        <Field label="학교 이메일" htmlFor="email">
          <EmailInput id="email" value={email} onChange={setEmail} required />
        </Field>
        <Field label="비밀번호" htmlFor="password">
          <Input id="password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </Field>
        <div className="-mt-2 text-right">
          <Link href="/forgot-password" className="text-[13px] text-ink-soft underline underline-offset-4">
            비밀번호를 잊으셨나요?
          </Link>
        </div>
        {error && <Notice tone="error">{error}</Notice>}
        <Button type="submit" size="lg" className="w-full" loading={loading}>
          로그인
        </Button>
      </form>
    </AuthFrame>
  );
}
