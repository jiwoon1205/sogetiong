"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { PreferencesForm } from "@/components/PreferencesForm";
import { SupportContact } from "@/components/SupportContact";
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
        <p className="mt-4 text-[13px] leading-relaxed text-ink-faint">
          학과 변경, 불편한 점, 그 밖의 문의는 메일로 보내주세요. <SupportContact prefix="" />
        </p>
        {/* 지금 보고 있는 화면이 어느 커밋으로 만든 것인지 (배포가 제대로 됐는지 확인용) */}
        <p className="mt-8 text-center text-[11.5px] text-ink-faint">
          버전 <span className="font-mono">{process.env.NEXT_PUBLIC_APP_VERSION || "dev"}</span>
        </p>
      </section>

      <DeleteAccount open={deleteOpen} onClose={() => setDeleteOpen(false)} onDone={() => router.replace("/")} />
    </div>
  );
}

// 탈퇴 후 다시 가입할 수 있을 때까지 (서버 설정 REJOIN_COOLDOWN_DAYS와 같은 값)
const REJOIN_DAYS = 7;

function rejoinDate(): string {
  const d = new Date(Date.now() + REJOIN_DAYS * 24 * 60 * 60 * 1000);
  return d.toLocaleString("ko-KR", { month: "long", day: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "Asia/Seoul" });
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
        <p className="text-[14.5px] font-semibold text-brick">탈퇴하면 되돌릴 수 없어요.</p>
        <ul className="list-disc space-y-1.5 pl-5 text-[14px] leading-relaxed text-ink-soft">
          <li>다른 사람에게는 바로 보이지 않아요. 공개 프로필, 관심사, 매칭 조건, 사진은 신고 확인을 위해 7일 동안 운영진만 볼 수 있게 보관한 뒤 자동으로 삭제돼요.</li>
          <li>진행 중인 대화는 모두 끝나요. 다시 가입해도 예전 매칭·대화·사진 평가는 돌아오지 않아요.</li>
          <li>생년월일·실명·학번 등 가입 정보와 채팅·신고 기록은 분쟁·신고 처리를 위해 일정 기간 보관한 뒤 삭제돼요.</li>
        </ul>
        <p className="text-[13px] leading-relaxed text-ink-faint">
          <b className="font-semibold text-ink-soft">{rejoinDate()} 이후</b> 같은 학교 메일로 다시 가입할 수 있어요 (탈퇴 후 {REJOIN_DAYS}일). 차단했던 상대는 다시 가입해도 계속 차단돼요.
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
