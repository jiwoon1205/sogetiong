"use client";

import { useSupportEmail } from "@/lib/catalog";

/** 문의 메일 주소 (A-15). 서버 설정 SUPPORT_EMAIL을 그대로 보여준다. */
export function SupportContact({ prefix = "문의" }: { prefix?: string }) {
  const email = useSupportEmail();
  if (!email) return null;
  return (
    <span>
      {prefix}{" "}
      <a href={`mailto:${email}`} className="underline underline-offset-4">
        {email}
      </a>
    </span>
  );
}
