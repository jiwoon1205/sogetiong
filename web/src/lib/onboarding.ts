import type { Me } from "@/lib/types";

/** 단계 번호 (2026-10-03: 가입비 단계 추가) */
export const STEP = { PROFILE: 0, PREFERENCES: 1, PAYMENT: 2, PHOTO: 3, DONE: -1 } as const;

/** 가입 후 어느 단계부터 할지. -1 = 모두 끝남 (사진 검수 대기·승인)
 *  2026-10-01: 중간에 나갔다 오면 사진 단계를 건너뛰게 되는 문제가 있어서 추가
 *  2026-10-03: 매칭 조건과 사진 사이에 가입비 입금 단계 (베타 회원은 건너뜀) */
export function firstStep(o: Me["onboarding"]): number {
  if (o.photo_approved) return STEP.DONE; // 예전에 승인된 사진이 있음 (재검토 반려 포함)
  if (!o.profile_done) return STEP.PROFILE;
  if (!o.preferences_done) return STEP.PREFERENCES;
  if (o.payment_required) return STEP.PAYMENT;
  if (o.photo_status === "PENDING" || o.photo_status === "IN_REVIEW" || o.photo_status === "APPROVED") return STEP.DONE;
  return STEP.PHOTO; // 사진 미제출·반려
}
