// ⑤ 프로필 정성 기준 (2026-10-24). 서버 backend/app/services/matching_service.py 의 BIO_FULL 등과 같은 숫자.
export const BIO_FULL = 150; // 자기소개: 띄어쓰기 빼고 150자 이상 (휴대폰에서 약 5줄)
export const IDEAL_FULL = 100; // 이상형: 100자 이상 (약 3~4줄)
export const TEXT_HALF = 30; // 30자 이상이면 절반 점수
export const INTEREST_MAX = 3; // 관심사는 최대 3개

/** 서버와 같은 방식으로 센 글자 수: 띄어쓰기·줄바꿈 제외, 같은 글자 반복(서로 다른 글자 10개 미만)은 0. */
export function effortChars(text: string | null | undefined): number {
  if (!text) return 0;
  const chars = Array.from(text).filter((c) => !/\s/.test(c));
  if (new Set(chars).size < 10) return 0;
  return chars.length;
}
