import type { MetadataRoute } from "next";

/**
 * "홈 화면에 추가" 설정 (웹 앱 매니페스트).
 * 홈 화면 아이콘으로 열면 주소창 없이 앱처럼 전체 화면으로 열린다 (안드로이드·아이폰 공통).
 * 아이콘 그림은 같은 폴더의 icon.png(512px), apple-icon.png(180px).
 */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "훕팅",
    short_name: "훕팅",
    description: "외대생끼리, 이름과 얼굴 대신 어떤 사람인지로 먼저 만나는 익명 소개팅.",
    lang: "ko",
    start_url: "/discover",
    scope: "/",
    display: "standalone",
    background_color: "#F6F3EE",
    theme_color: "#F6F3EE",
    icons: [
      { src: "/icon.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/apple-icon.png", sizes: "180x180", type: "image/png" },
    ],
  };
}
