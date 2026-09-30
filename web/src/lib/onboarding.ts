import type { Me } from "@/lib/types";

/** 가입 후 어느 단계부터 할지 (0 프로필, 1 매칭 조건, 2 사진). -1 = 모두 끝남 (사진 검수 대기·승인)
 *  2026-10-01: 중간에 나갔다 오면 사진 단계를 건너뛰게 되는 문제가 있어서 추가 */
export function firstStep(o: Me["onboarding"]): number {
  if (o.photo_approved) return -1; // 예전에 승인된 사진이 있음 (재검토 반려 포함)
  if (!o.profile_done) return 0;
  if (!o.preferences_done) return 1;
  if (o.photo_status === "PENDING" || o.photo_status === "IN_REVIEW" || o.photo_status === "APPROVED") return -1;
  return 2; // 사진 미제출·반려
}
