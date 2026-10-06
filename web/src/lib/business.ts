/**
 * 사업자 정보 (2026-10-06).
 * 전자상거래법 제10조: 사이버몰 첫 화면에 상호·대표자·주소·전화·이메일·사업자등록번호·통신판매업 신고번호·
 * 이용약관·호스팅 제공자를 보여줘야 한다.
 * 바뀌면 여기와 deploy/static/terms.html, deploy/static/privacy.html 을 같이 고친다.
 */
export const BUSINESS = {
  name: "훕팅",
  owner: "정지운",
  registrationNumber: "570-22-02299",
  // 간이과세자 등 신고 면제 대상 (2026-10-06). 신고하면 "제2026-서울구로-0000호" 같은 번호로 바꾼다
  mailOrderNumber: "신고 면제 대상",
  address: "서울 구로구 공원로 40",
  phone: "070-7692-5737",
  email: "support@private-matching.com",
  hosting: "Google Cloud",
} as const;
