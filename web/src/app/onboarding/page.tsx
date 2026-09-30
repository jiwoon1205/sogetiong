"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AuthFrame } from "@/components/AuthFrame";
import { PhotoUpload } from "@/components/PhotoUpload";
import { PreferencesForm } from "@/components/PreferencesForm";
import { ProfileForm } from "@/components/ProfileForm";
import { Steps } from "@/components/Steps";
import { PageTitle, Spinner } from "@/components/ui";
import { useCatalog } from "@/lib/catalog";
import { SessionGate, useSession } from "@/lib/session";
import { firstStep } from "@/lib/onboarding";

export default function OnboardingPage() {
  return (
    <SessionGate fallback={<Spinner />}>
      <Onboarding />
    </SessionGate>
  );
}

function Onboarding() {
  const router = useRouter();
  const { me, refresh } = useSession();
  const { campuses, interests, loaded } = useCatalog(me.university_id);
  // 멈췄던 단계부터 이어서 한다 (예전에는 들어올 때마다 1단계부터 시작)
  const [step, setStep] = useState(() => firstStep(me.onboarding));
  const finished = step === -1;

  // 이미 사진까지 냈으면(검수 대기·승인) 가입 과정은 끝났으므로 추천 화면으로
  useEffect(() => {
    if (finished) router.replace("/discover");
  }, [finished, router]);

  if (!loaded || finished) return <Spinner />;

  return (
    <AuthFrame>
      <Steps labels={["프로필", "매칭 조건", "사진"]} current={step} className="mb-9" />

      {step === 0 && (
        <>
          <PageTitle title="나를 소개해주세요" desc="사진 대신 이 내용으로 먼저 만나게 돼요. 나중에 언제든 고칠 수 있어요." />
          <ProfileForm campuses={campuses} interests={interests} submitLabel="다음" onSaved={() => setStep(1)} />
        </>
      )}

      {step === 1 && (
        <>
          <PageTitle title="어떤 사람을 만나고 싶나요" />
          <PreferencesForm campuses={campuses} submitLabel="다음" onSaved={() => setStep(2)} />
        </>
      )}

      {step === 2 && (
        <>
          <PageTitle title="사진을 1~3장 제출해주세요" desc="AI가 전체적인 인상·스타일·자기관리·사진 분위기를 평가해요." />
          <PhotoUpload
            onUploaded={async () => {
              await refresh();
              router.replace("/discover");
            }}
          />
        </>
      )}
    </AuthFrame>
  );
}

