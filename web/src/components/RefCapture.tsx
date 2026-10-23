"use client";

import { useEffect } from "react";
import { saveRefFromUrl } from "@/lib/referral";

/** 어느 페이지로 들어오든 주소의 ?ref= 초대 코드를 기억한다 (2026-10-24 친구 초대 이벤트). 화면에는 아무것도 안 그린다. */
export function RefCapture() {
  useEffect(() => {
    saveRefFromUrl();
  }, []);
  return null;
}
