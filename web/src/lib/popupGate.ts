"use client";

/**
 * 팝업이 한 번에 하나만 뜨게 (2026-11-24).
 * 앱을 열었을 때(이번 페이지 로드) 설문·찾는 관계·공지·매칭 팁 중 하나라도 떴으면 기록해 둔다.
 * 앱 설치 안내 팝업은 이번 로드에 다른 팝업이 하나도 없었을 때만 뜬다 → 다른 팝업을 닫고 "다음에 들어왔을 때" 뜬다.
 * (페이지를 새로 열면 기록이 지워진다)
 */
let otherPopupThisLoad = false;

export function markOtherPopup() {
  otherPopupThisLoad = true;
}

export function hadOtherPopup(): boolean {
  return otherPopupThisLoad;
}
