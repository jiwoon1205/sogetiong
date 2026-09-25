"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { PreferencesForm } from "@/components/PreferencesForm";
import { Button, Field, Input, Modal, Notice, PageTitle, Spinner } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { useCatalog } from "@/lib/catalog";
import { useSession } from "@/lib/session";

export default function SettingsPage() {
  const router = useRouter();
  const { me } = useSession();
  const { campuses, loaded } = useCatalog(me.university_id);
  const [deleteOpen, setDeleteOpen] = useState(false);

  async function logout() {
    await api("/auth/logout", { method: "POST" }).catch(() => {});
    router.replace("/");
  }

  if (!loaded) return <Spinner />;

  return (
    <div className="mx-auto max-w-app">
      <PageTitle eyebrow="설정" title="매칭 조건" desc="바꾼 조건은 다음 추천부터 반영돼요." />
      <PreferencesForm campuses={campuses} />

      <section className="mt-14">
        <p className="eyebrow mb-4">계정</p>
        <div className="divide-y divide-line rounded-card border border-line bg-paper-card">
          <div className="flex items-center justify-between px-5 py-4">
            <div>
              <p className="text-[13px] text-ink-faint">학교 이메일 · 나만 볼 수 있어요</p>
              <p className="mt-0.5 text-[14.5px]">{me.email}</p>
            </div>
          </div>
          <button onClick={logout} className="block w-full px-5 py-4 text-left text-[14.5px] hover:bg-paper-deep/60">
            로그아웃
          </button>
          <button onClick={() => setDeleteOpen(true)} className="block w-full px-5 py-4 text-left text-[14.5px] text-brick hover:bg-brick-wash/50">
            탈퇴하기
          </button>
        </div>
      </section>

      <DeleteAccount open={deleteOpen} onClose={() => setDeleteOpen(false)} onDone={() => router.replace("/")} />
    </div>
  );
}

function DeleteAccount({ open, onClose, onDone }: { open: boolean; onClose: () => void; onDone: () => void }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await api("/me", { method: "DELETE", body: { password } });
      onDone();
    } catch (err) {
      setError(errorMessage(err));
      setLoading(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="탈퇴하기">
      <form onSubmit={submit} className="space-y-4">
        <p className="text-[14px] leading-relaxed text-ink-soft">
          공개 프로필, 매칭 조건, 사진이 삭제되고 진행 중인 대화가 모두 끝나요. 신고 처리 등 법적으로 보관해야 하는 기록은 정해진 기간 동안만 보관돼요.
        </p>
        <Field label="비밀번호 확인" htmlFor="del-pw">
          <Input id="del-pw" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </Field>
        {error && <Notice tone="error">{error}</Notice>}
        <Button type="submit" variant="danger" className="w-full" loading={loading}>
          탈퇴하기
        </Button>
      </form>
    </Modal>
  );
}
