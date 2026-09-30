"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { AuthFrame } from "@/components/AuthFrame";
import { PhotoUpload } from "@/components/PhotoUpload";
import { PreferencesForm } from "@/components/PreferencesForm";
import { ProfileForm } from "@/components/ProfileForm";
import { Steps } from "@/components/Steps";
import { PageTitle, Spinner } from "@/components/ui";
import { useCatalog } from "@/lib/catalog";
import { SessionGate, useSession } from "@/lib/session";

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
  const [step, setStep] = useState(0);

  if (!loaded) return <Spinner />;

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
          <PageTitle title="사진 한 장을 제출해주세요" desc="운영진이 확인한 뒤 전체적인 인상·스타일·자기관리·사진 분위기를 평가해요." />
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
